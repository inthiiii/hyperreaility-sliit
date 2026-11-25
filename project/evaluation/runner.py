"""Paired workflow attempts scored by the isolated, approval-gated evaluator.

Benchmark approvals use an explicitly labelled automated test operator. They are
not real human approvals. The evaluator's truth and future events never enter a
coordinator payload; only reached visible checkpoints are supplied on replans.
"""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import platform
from pathlib import Path
import random
import time
from datetime import datetime, timezone
from uuid import uuid4

from project.core.coordinator import Coordinator, approve_run
from project.core.orchestrator import AgentOrchestrator
from project.evaluation.extraction import truth_extraction_metrics
from project.core.schemas import ScenarioInput, SimulationResult
from project.core.state import digest
from project.data.loader import CaseLoader
from project.data.evaluator import EvaluatorLoader
from project.simulation.episode import IncidentEpisode
from project.llm.client import HostedAdapter, RunBudget, BudgetExceeded
from project.llm.health import preflight
from project.agents.protocol import protocol_manifest, PROTOCOL_VERSION
from project.evaluation.comparison import paired_summary

VARIANTS = {
    'heuristic': ('template', 'greedy', True, True),
    'optimizer': ('template', 'cp_sat', True, True),
    'single': ('single', 'cp_sat', True, True),
    'multi': ('multi', 'cp_sat', True, True),
    'no_reviewer': ('multi', 'cp_sat', False, True),
    'no_feedback': ('multi', 'cp_sat', True, False),
    # Legacy v13 matched pipeline (same four stages, role label only): kept as a control.
    'matched_single': ('single', 'cp_sat', True, True),
    'matched_multi': ('multi', 'cp_sat', True, True),
}
LEGACY_VARIANTS = {'matched_single', 'matched_multi'}


def workflow_for(variant):
    """Hosted variants use the v14 agent orchestrator unless explicitly legacy."""
    return Coordinator if variant in LEGACY_VARIANTS else AgentOrchestrator
DATA_ROOT = Path(__file__).resolve().parents[2] / 'data'
LIMITS = {'max_calls': 12, 'max_input_tokens': 24000, 'max_output_tokens': 4800, 'max_seconds': 180}


def source_hash():
    root = Path(__file__).resolve().parents[1]
    return digest({str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(root.rglob('*.py'))})


def _save(path, payload):
    encoded = json.dumps(payload, indent=2, allow_nan=False) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True,mode=0o700)
    with open(path,'x',encoding='utf-8',newline='\n',opener=lambda p,flags:os.open(p,flags,0o600)) as stream:
        stream.write(encoded)


def _remaining_budget(started, used):
    remaining = {
        'max_calls': LIMITS['max_calls'] - used['calls'],
        'max_input_tokens': LIMITS['max_input_tokens'] - used['input'],
        'max_output_tokens': LIMITS['max_output_tokens'] - used['output'],
        'max_seconds': LIMITS['max_seconds'] - (time.monotonic() - started),
    }
    if any(value <= 0 for value in remaining.values()):
        raise BudgetExceeded('Whole-incident benchmark budget exhausted')
    return RunBudget(**remaining)


def _check_time(started):
    if time.monotonic() - started >= LIMITS['max_seconds']:
        raise BudgetExceeded('Whole-incident benchmark time exhausted')


def _score(result, case):
    """A prefix is never a final score, even if it contains a numeric downtime."""
    if result.run_metadata.get('measurement_scope') != 'complete_incident':
        raise ValueError('Final independent score requires complete incident coverage')
    metrics = result.metrics
    if metrics.get('horizon_min') != case.horizon_min or metrics.get('measured_duration_min') != case.horizon_min:
        raise ValueError('Evaluator did not cover the full incident horizon')
    total = sum(service.weight for service in case.services) * case.horizon_min
    for field in ('weighted_downtime_min', 'weighted_available_min', 'total_weighted_horizon_min'):
        value = metrics.get(field)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('Invalid independent metric')
    if (metrics['total_weighted_horizon_min'] != total or
            not math.isclose(metrics['weighted_downtime_min'] + metrics['weighted_available_min'], total, abs_tol=1e-9)):
        raise ValueError('Independent service-minute accounting does not balance')
    return {
        'actual_weighted_downtime': metrics['weighted_downtime_min'],
        'actual_weighted_available_minutes': metrics['weighted_available_min'],
        'actual_unweighted_available_minutes': metrics.get('unweighted_available_min'),
        'actual_unweighted_downtime_minutes': metrics.get('unweighted_downtime_min'),
        'actual_critical_service_downtime_minutes': metrics.get('critical_service_downtime_min'),
        'actual_first_restoration_min': metrics.get('first_restoration_min'),
        'actual_services_available_at_horizon_end': metrics.get('services_available_at_horizon_end'),
        'actual_unmet_needs_count': metrics.get('unmet_needs_count'),
        'baseline_weighted_downtime': metrics.get('baseline_weighted_downtime_min'),
        'measured_duration_min': metrics['measured_duration_min'],
    }


def model_configuration():
    health=preflight()
    return {'provider':health['provider'],'model':health['model'],
            'endpoint_sha256':digest(os.environ.get('LLM_BASE_URL','')),
            'api_mode':health.get('api_mode','chat_completions'),'reasoning_effort':health.get('reasoning_effort'),'response_format':'json_schema' if health.get('api_mode')=='responses' else 'json_object','temperature':'provider_default',
            'sdk_retries':0,'schema_repair_attempts':1,'protocol_version':PROTOCOL_VERSION}


def _attempt(case, variant, repeat, output, data_root, max_episodes, configuration=None):
    mode, planner, reviewer, feedback = VARIANTS[variant]
    started = time.monotonic()
    used = {'calls': 0, 'input': 0, 'output': 0}
    usage = []
    auxiliary = []
    episode = None
    scenario = case
    version = 1
    row = {'job_id': str(uuid4()), 'scenario_id': case.scenario_id, 'variant': variant, 'repeat': repeat,
           'status': 'failed', 'plan_feasible': False, 'model_calls': 0,
           'actual_weighted_downtime': None, 'scoring_status': 'not_scored_failed',
           'approval_mode': 'automated_benchmark_operator', 'approved_episodes': 0,
           'run_ids': [], 'episode_artifacts': [], 'model_usage': [], 'api_cost': None,
           'failure_phase': None,'model_configuration':configuration,'decision_effect_count':0}
    phase = 'planning'
    try:
        for episode_number in range(max_episodes):
            phase = 'budget'
            budget = _remaining_budget(started, used)
            adapter = None
            result = None
            phase = 'planning'
            try:
                if mode != 'template':
                    if model_configuration()!=configuration:raise ValueError('Hosted configuration changed during the experiment')
                    adapter = HostedAdapter.from_env(budget=budget)
                    if (adapter.provider,adapter.model,getattr(adapter,'reasoning_effort',None),getattr(adapter,'api_mode','chat_completions'))!=(configuration['provider'],configuration['model'],configuration['reasoning_effort'],configuration['api_mode']):
                        raise ValueError('Hosted adapter does not match the frozen model configuration')
                result = workflow_for(variant)(adapter, budget=budget, planner=planner, reviewer_enabled=reviewer,
                    feedback_enabled=feedback, trace_dir=output/'runs').run(scenario, mode, state_version=version)
            finally:
                # Capture attempts even if client construction, a workflow or cleanup fails.
                usage.extend(dict(item) for item in budget.records)
                auxiliary.extend(dict(item) for item in budget.auxiliary_records)
                used['calls'] += budget.calls
                used['input'] += max(budget.input_reserved, sum(r.get('input_tokens', 0) for r in budget.records))
                used['output'] += max(budget.output_reserved, sum(r.get('output_tokens', 0) for r in budget.records))
                if adapter is not None:
                    try:
                        adapter.close()
                    except Exception as error:
                        row.setdefault('cleanup_errors', []).append(type(error).__name__)
            _check_time(started)
            row['decision_effect_count']+=len(result.metadata.get('decision_effects',[]))
            row['run_id'] = result.run_id
            row['run_ids'].append(result.run_id)
            row['plan_feasible'] = bool(result.validation and result.validation.valid)
            if result.status != 'awaiting_approval':
                row.update(status='escalated', scoring_status='not_scored_escalated',
                           escalation_reasons=result.reasons)
                break
            phase = 'approval'
            approval = approve_run(result, 'Automated benchmark operator')
            phase = 'evaluator_input_binding'
            if episode is None:
                # A shared scenario ID alone must never pair unrelated input and truth.
                loader = CaseLoader(data_root/'processed/agent_inputs')
                canonical = loader.load_case(loader.find(case.scenario_id))
                if digest(canonical) != digest(case):
                    raise ValueError('Benchmark input differs from its registered evaluator case')
                truth = EvaluatorLoader(data_root/'evaluation/ground_truth').load(case.scenario_id)
                row['evaluator_truth_hash'] = digest(truth)
                if episode_number == 0 and result.metadata.get('raw_facts') is not None:
                    # Scored on the evaluator side; agents never see these labels.
                    row['extraction'] = truth_extraction_metrics(truth, result.metadata['raw_facts'],
                                                                 result.metadata.get('final_facts'), result.metadata)
                episode = IncidentEpisode(case, truth)
            phase = 'simulation'
            raw = episode.advance(scenario, result.plan, approval, state=result.state)
            simulation = SimulationResult.model_validate(raw)
            if (simulation.scenario_id, simulation.plan_id, simulation.state_version) != (
                    case.scenario_id, result.plan.plan_id, result.state.state_version):
                raise ValueError('Evaluator output identity mismatch')
            # Validate raw numbers before JSON-mode serialization could turn NaN/Inf into null.
            def finite_tree(value):
                if isinstance(value, float) and not math.isfinite(value): raise ValueError('Non-finite evaluator output')
                if isinstance(value, dict):
                    for item in value.values(): finite_tree(item)
                if isinstance(value, (list, tuple)):
                    for item in value: finite_tree(item)
            finite_tree(simulation.model_dump(mode='python'))
            _check_time(started)
            row['approved_episodes'] += 1
            relative = Path('simulations') / (row['job_id'] + f'-{episode_number}.json')
            _save(output/relative, {'job_id': row['job_id'], 'run_id': result.run_id,
                'approval_mode': row['approval_mode'], 'approval': approval.model_dump(mode='json'),
                'state_hash': digest(result.state), 'result_hash': digest(simulation),
                'result': simulation.model_dump(mode='json')})
            row['episode_artifacts'].append(relative.as_posix())
            if episode.complete:
                phase = 'score_validation'
                row.update(_score(simulation, case))
                row.update(status='completed', scoring_status='scored')
                break
            if not episode.paused or not simulation.run_metadata.get('replan_required'):
                raise ValueError('Evaluator stopped without completion or a replan checkpoint')
            scenario = episode.checkpoint()
            if scenario.current_time_min <= result.state.scenario.current_time_min:
                raise ValueError('Incident checkpoint did not advance')
            version = result.state.state_version + 1
        else:
            row.update(status='incomplete', scoring_status='not_scored_episode_limit', failure_phase='episode_limit')
    except Exception as error:
        row.update(status='failed', scoring_status='not_scored_failed',
                   failure_phase=phase, error_type=type(error).__name__)
        # Do not leave a score from any failed/incomplete path.
        row['actual_weighted_downtime'] = None
    finally:
        row['model_calls'] = used['calls']
        row['model_usage'] = usage
        row['auxiliary_requests']=auxiliary
        row['auxiliary_request_count']=len(auxiliary)
        row['returned_models']=sorted({r['returned_model'] for r in usage if r.get('returned_model')})
        row['input_tokens'] = sum(r.get('input_tokens', 0) for r in usage) if used['calls'] == len(usage) and all('input_tokens' in r for r in usage) else None
        row['output_tokens'] = sum(r.get('output_tokens', 0) for r in usage) if used['calls'] == len(usage) and all('output_tokens' in r for r in usage) else None
        row['usage_complete'] = row['input_tokens'] is not None and row['output_tokens'] is not None
        row['input_reserved_upper_bound'] = used['input']
        row['output_reserved_upper_bound'] = used['output']
        row['duration_seconds'] = time.monotonic() - started
    return row


def run_benchmark(paths, output, variants=('heuristic', 'optimizer'), repeats=3, seed=22,
                  allow_live=False, *, data_root=None, max_episodes=10, review_release=None, allow_ai_reviewed=False):
    if type(repeats) is not int or repeats < 1:
        raise ValueError('Repeats must be positive integers')
    if not variants or any(v not in VARIANTS for v in variants):
        raise ValueError('Unknown or empty variant list')
    if len(set(variants)) != len(variants):
        raise ValueError('Duplicate variants')
    if type(max_episodes) is not int or not 1 <= max_episodes <= 100:
        raise ValueError('Episode limit must be an integer in [1,100]')
    paths=list(map(Path,paths))
    cases = [ScenarioInput.model_validate_json(p.read_text()) for p in paths]
    if not cases or len({c.scenario_id for c in cases}) != len(cases):
        raise ValueError('Provide unique visible scenario IDs')
    data_root = Path(data_root or DATA_ROOT).resolve()
    registered_ids={p.stem for p in (data_root/'processed/agent_inputs/candidate_evaluation').glob('*.json')}
    candidate_cases=[case for case,path in zip(cases,paths) if case.scenario_id in registered_ids
                     or case.scenario_id.startswith('EVAL-') or path.parent.name=='candidate_evaluation']
    review_gate=None
    if candidate_cases:
        if review_release is None:
            raise ValueError('Candidate evaluation is blocked until independent human review is recorded; supply --review-release')
        if allow_ai_reviewed:
            from project.evaluation.ai_case_review import validate_release
        else:
            from project.evaluation.case_review import validate_release
        review_gate=validate_release(data_root.parent,review_release,candidate_cases)
    hosted = any(VARIANTS[v][0] != 'template' for v in variants)
    if hosted and (not allow_live or preflight()['status'] == 'blocked'):
        raise ValueError('Hosted benchmarks require --allow-live and a configured model/key')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True,mode=0o700)
    configuration=model_configuration() if hosted else None
    manifest = {'format_version': 3, 'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'source_sha256': source_hash(), 'cases': {c.scenario_id: digest(c) for c in cases},
        'variants': list(variants), 'repeats': repeats, 'order_seed': seed,
        'model_configuration': configuration, 'comparison_protocol':protocol_manifest(),
        'runtime':{'python':platform.python_version(),'platform':platform.platform(),'machine':platform.machine()},
        'packages': {name: importlib.metadata.version(name) for name in ('pydantic', 'ortools', 'networkx', 'openai')},
        'scoring_status': 'independent_incident_evaluator_connected',
        'approval_mode': 'automated_benchmark_operator', 'whole_incident_limits': LIMITS,
        'max_episodes': max_episodes, 'evaluation_review':review_gate,
        'scope': 'Matched tool-assisted workflow comparison. Template baselines are not LLM agents. Independent held-out review remains a separate gate; development results do not establish superiority.'}
    _save(output/'manifest.json', manifest)
    jobs = [(c, v, n) for c in cases for n in range(repeats) for v in variants]
    random.Random(seed).shuffle(jobs)
    rows = []
    with open(output/'attempts.jsonl','x',encoding='utf-8',opener=lambda p,flags:os.open(p,flags,0o600)) as stream:
        for case, variant, repeat in jobs:
            row = _attempt(case, variant, repeat, output, data_root, max_episodes,configuration)
            encoded = json.dumps(row, allow_nan=False)
            rows.append(row)
            stream.write(encoded + '\n');stream.flush()
    columns = sorted({key for row in rows for key in row})
    with open(output/'attempts.csv','x',newline='',encoding='utf-8',opener=lambda p,flags:os.open(p,flags,0o600)) as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator='\n');writer.writeheader()
        writer.writerows({key: json.dumps(value) if isinstance(value, (dict, list)) else value
                         for key, value in row.items()} for row in rows)
    _save(output/'comparison.json',paired_summary(rows))
    _save(output/'summary.json', {'attempts': len(rows),
        'scored': sum(r['scoring_status'] == 'scored' for r in rows),
        'escalated': sum(r['status'] == 'escalated' for r in rows),
        'failed': sum(r['status'] == 'failed' for r in rows),
        'incomplete': sum(r['status'] == 'incomplete' for r in rows),
        'claims_multi_agent_superiority': False})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenarios', nargs='+', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--variants', nargs='+', choices=list(VARIANTS), default=['heuristic', 'optimizer'])
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--seed', type=int, default=22)
    parser.add_argument('--allow-live', action='store_true')
    parser.add_argument('--data-root', type=Path)
    parser.add_argument('--max-episodes', type=int, default=10)
    parser.add_argument('--review-release',type=Path,help='Hash-bound completed review release for evaluation candidates')
    parser.add_argument('--allow-ai-reviewed',action='store_true',help='Explicitly allow AI-self-reviewed synthetic engineering cases; does not establish independent held-out validity')
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2]/'.env')
    rows = run_benchmark(args.scenarios, args.output, args.variants, args.repeats, args.seed, args.allow_live,
                         data_root=args.data_root, max_episodes=args.max_episodes,review_release=args.review_release,allow_ai_reviewed=args.allow_ai_reviewed)
    print(json.dumps({'attempts': len(rows), 'scored': sum(r['scoring_status'] == 'scored' for r in rows),
                      'scoring_status': 'independent_incident_evaluator_connected'}, indent=2))

if __name__ == '__main__':
    main()
