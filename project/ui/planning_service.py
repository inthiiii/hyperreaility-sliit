"""Explicit, per-session planning actions. Never invoke from passive rendering."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

from project.core.coordinator import Coordinator
from project.core.orchestrator import AgentOrchestrator
from project.core.state import digest
from project.core.tracing import redact
from project.llm.client import HostedAdapter
from project.llm.health import preflight

MODES = ('template', 'single', 'multi')
# Hosted modes run the v14 agent orchestrator; the v13 matched pipeline stays available as a control.
HOSTED_WORKFLOW = AgentOrchestrator
PLANNERS = ('cp_sat', 'greedy')


def request_key(session, choice, mode, planner):
    settings = None
    if mode != 'template':
        health = preflight()
        settings = {'provider': health['provider'], 'model': health['model'],'reasoning_effort':health.get('reasoning_effort'),'api_mode':health.get('api_mode','chat_completions'),
                    'endpoint_hash': digest(os.environ.get('LLM_BASE_URL', ''))}
    return digest({'input': choice.content_hash, 'path': choice.key,
                   'mode': mode, 'planner': planner, 'settings': settings,
                   'generation': session.planning_generation})


def _save_attempt(attempt, root):
    """Separate metadata-only records for setup/workflow failures, including usage."""
    directory = Path(root) / 'results/local_runs/ui_attempts'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (attempt['attempt_id'] + '.json')
    temporary = directory / ('.' + attempt['attempt_id'] + '.tmp')
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(redact(attempt), stream, indent=2)
            stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_plan(session, choice, mode, planner, root, *, adapter_factory=None, coordinator_factory=None):
    """At most one execution per request key; exceptions never silently retry/fallback."""
    if mode not in MODES or planner not in PLANNERS:
        raise ValueError('Unknown planning mode or scheduler')
    if (session.selected_key, session.scenario_hash) != (choice.key, choice.content_hash):
        raise ValueError('Scenario selection is stale')
    if digest(choice.scenario) != choice.content_hash:
        raise ValueError('Scenario content changed after validation')
    if session.busy:
        return 'busy'
    key = request_key(session, choice, mode, planner)
    if key in session.planning_requests:
        return 'duplicate'
    # Record the request before any client construction or inference.
    session.planning_requests.add(key)
    session.busy = True
    session.core.current = None
    session.core.approval = None
    session.simulation_result = None
    session.last_decision = None
    session.review_feedback = None
    session.simulation_attempt = None
    attempt = {'format_version': 1, 'attempt_id': str(uuid4()), 'request_key': key,
               'started_at_utc': datetime.now(timezone.utc).isoformat(),
               'scenario_id': choice.scenario.scenario_id, 'input_hash': choice.content_hash,
               'mode': mode, 'planner': planner, 'status': 'starting', 'model_usage': [],
               'warnings': [], 'run_id': None}
    session.planning_attempt = attempt
    adapter = None
    phase = 'configuration'
    try:
        if mode != 'template':
            health = preflight()
            if health['status'] == 'blocked':
                attempt.update(status='blocked', error_code='configuration_incomplete', reasons=health['reasons'])
                return 'blocked'
            attempt['configured_provider'] = health['provider']
            attempt['configured_model'] = health['model']
            attempt['configured_api_mode'] = health.get('api_mode','chat_completions')
            attempt['configured_reasoning_effort'] = health.get('reasoning_effort')
            phase = 'client_setup'
            adapter = (adapter_factory or HostedAdapter.from_env)()
        phase = 'planning'
        coordinator = (coordinator_factory or (Coordinator if mode == 'template' else HOSTED_WORKFLOW))(adapter, planner=planner,
                                 trace_dir=Path(root) / 'results/local_runs')
        result = session.core.prepare(coordinator, choice.scenario.model_copy(deep=True), mode)
        if result.state.source_hash != choice.content_hash or result.state.scenario_id != choice.scenario.scenario_id:
            raise ValueError('Coordinator returned a different scenario')
        attempt.update(status=result.status, run_id=result.run_id)
        return result.status
    except Exception as error:
        # Never expose raw provider exceptions, URLs, headers or keys in the UI.
        session.core.current = None
        session.core.approval = None
        attempt.update(status='failed', error_code=phase + '_failed', error_type=type(error).__name__)
        return 'failed'
    finally:
        if adapter is not None:
            attempt['model_usage'] = list(adapter.budget.records)
            attempt['auxiliary_requests'] = list(adapter.budget.auxiliary_records)
            try:
                adapter.close()
            except Exception as error:
                attempt['warnings'].append('Provider cleanup failed (' + type(error).__name__ + '); no request was retried.')
        attempt['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        try:
            _save_attempt(attempt, root)
        except Exception:
            attempt['warnings'].append('Attempt metadata could not be saved. No automatic retry was made.')
        session.busy = False


def begin_new_attempt(session):
    if session.busy:
        raise ValueError('Wait for the current planning request to finish')
    session.planning_generation += 1
    session.planning_attempt = None
    session.core.current = None
    session.core.approval = None
    session.simulation_result = None
    session.last_decision = None
    session.review_feedback = None
    session.simulation_attempt = None


def schedule_rows(result):
    if result.plan is None:
        return []
    return [{'Action': action.action_id, 'Kind': action.kind.replace('_', ' '),
             'Target': action.target_id, 'Crew': action.crew_id, 'Generator': action.generator_id or '—',
             'Depart (min)': action.departure_min, 'Route': ' → '.join(action.travel_route),
             'Work start (min)': action.work_start_min, 'Work end (min)': action.work_end_min,
             'Work duration (min)': action.work_end_min - action.work_start_min}
            for action in result.plan.actions]


def timeline_rows(result):
    if result.plan is None:
        return []
    rows = []
    for action in result.plan.actions:
        base = {'Lane': action.crew_id + ' · ' + action.action_id, 'Action': action.action_id,
                'Target': action.target_id, 'Kind': action.kind.replace('_', ' ')}
        if action.work_start_min > action.departure_min:
            rows.append(dict(base, Stage='Travel', Start=action.departure_min, End=action.work_start_min))
        rows.append(dict(base, Stage='Work', Start=action.work_start_min, End=action.work_end_min))
    return rows


def fact_rows(result):
    superseded={rid for report in result.state.scenario.reports for rid in report.supersedes_report_ids}
    return [{'Asset': fact.target_type + ':' + fact.target_id, 'Attribute': fact.attribute,
             'Value': 'Unknown' if fact.value is None else 'True' if fact.value else 'False',
             'Resolver status': 'superseded confirmation' if set(fact.evidence_ids)&superseded else fact.status, 'Evidence': ', '.join(fact.evidence_ids),
             'Observed (min)': fact.observed_at_min, 'Received (min)': fact.received_at_min,
             'Reason': fact.reason} for fact in result.state.facts]
