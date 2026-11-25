"""RE:L!NK agent workflow, protocol relink-agents-v14.

Differences from the v13 matched pipeline kept in ``coordinator.py``:

* Specialists see role-scoped views and exchange typed messages; the reviewer
  re-checks facts against raw reports in its own context.
* The single-agent baseline is one agent with one accumulating context that does
  every job, then reviews its own plan. Same model, tools, evidence and budget.
* Facts are checked without fixture labels: IDs, attribute type and timestamps
  are verified, and authority comes from the cited source, not from the model.
* Unknown or conflicting facts do not stop the run. The scheduler treats them
  as unavailable, the plan covers what is certain and the operator gets
  targeted questions. Whole-run escalation is kept for genuine unsafe review,
  exhausted budgets and API failures.

The coordinator, scheduler, validator and resolver are software, not agents.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from uuid import uuid4

from project.agents import registry as R
from project.agents.context import arithmetic_checks, plan_view
from project.core.coordinator import Coordinator, RunResult
from project.core.forecast import service_forecast
from project.core.planner import greedy_plan, plan as cp_sat_plan
from project.core.schemas import EvidenceFact
from project.core.state import build_verified_state, digest
from project.core.validator import validate
from project.llm.client import RunBudget

MAX_REVISIONS = 3
ATTRIBUTE_TYPES = {'site': ('equipment_ok', 'grid_power_ok'), 'link': ('backhaul_ok',), 'road': ('open',)}


def normalize_facts(scenario, facts):
    """Accept well-formed claims; authority and timestamps come from the cited reports.

    Returns (accepted, rejected) where rejected entries carry a reason. Nothing
    here consults evaluator labels.
    """
    reports = {r.report_id: r for r in scenario.reports}
    targets = {'site': {s.site_id for s in scenario.sites}, 'link': {l.link_id for l in scenario.links},
               'road': {r.road_id for r in scenario.roads}}
    accepted, rejected, seen = [], [], {}
    for fact in facts:
        reason = None
        cited = [reports.get(rid) for rid in fact.evidence_ids]
        if not fact.evidence_ids or None in cited:
            reason = 'cites an unknown report'
        elif fact.target_id not in targets[fact.target_type]:
            reason = f'unknown {fact.target_type} ID {fact.target_id}'
        elif fact.attribute not in ATTRIBUTE_TYPES[fact.target_type]:
            reason = f'attribute {fact.attribute} does not apply to a {fact.target_type}'
        elif fact.value is None:
            reason = 'a claim needs a true/false value; unknowns stay unknown without a fact'
        if reason:
            rejected.append({'fact': fact.model_dump(), 'reason': reason})
            continue
        verified = all(r.source_type in R.AUTHORITATIVE_SOURCES for r in cited)
        clean = EvidenceFact(target_type=fact.target_type, target_id=fact.target_id, attribute=fact.attribute,
                             value=fact.value, evidence_ids=sorted(set(fact.evidence_ids)),
                             observed_at_min=max(r.observed_at_min for r in cited),
                             received_at_min=max(r.received_at_min for r in cited),
                             status='verified' if verified else 'unverified', reason=fact.reason[:200])
        key = (tuple(clean.evidence_ids), clean.target_type, clean.target_id, clean.attribute)
        if key in seen:
            if seen[key].value != clean.value:
                rejected.append({'fact': fact.model_dump(), 'reason': 'same report claimed with both values'})
                accepted = [f for f in accepted if f is not seen[key]]
            continue
        seen[key] = clean
        accepted.append(clean)
    return accepted, rejected


def unresolved_questions(state):
    names = {s.site_id: s.label for s in state.scenario.sites}
    out = []
    for item in state.unresolved_facts:
        parts = item.split(':')
        target = parts[1]
        what = parts[2].replace('_ok', '').replace('_', ' ') if len(parts) > 2 else ('backhaul' if parts[0] == 'link' else 'road access')
        label = f'{target} ({names[target]})' if target in names else target
        out.append({'source': 'evidence_resolver', 'target_id': target,
                    'question': f'Status of {what} at {label} is unknown or conflicting. Please confirm.',
                    'evidence_ids': [f.evidence_ids[0] for f in state.facts if f.target_id == target][:3]})
    return out


class AgentOrchestrator:
    """Drop-in replacement for ``Coordinator`` for hosted modes ``single`` and ``multi``."""

    def __init__(self, adapter=None, budget=None, planner='cp_sat', *, reviewer_enabled=True,
                 feedback_enabled=True, trace_dir=None):
        self.adapter = adapter
        self.budget = budget or (adapter.budget if adapter else RunBudget())
        if adapter and adapter.budget is not self.budget:
            raise ValueError('Adapter and orchestrator must share one budget')
        if planner not in ('cp_sat', 'greedy'):
            raise ValueError('Unknown planner')
        self.planner = planner
        self.reviewer_enabled = reviewer_enabled
        self.feedback_enabled = feedback_enabled
        self.trace_dir = trace_dir
        self._used = False

    # ------------------------------------------------------------------ run
    def run(self, scenario, mode='multi', state_version=1):
        if mode == 'template':
            return Coordinator(None, budget=self.budget, planner=self.planner, trace_dir=self.trace_dir).run(
                scenario, 'template', state_version=state_version)
        if mode not in ('single', 'multi'):
            raise ValueError('Unknown mode')
        if self._used:
            raise ValueError('Use a fresh orchestrator for each run')
        if self.adapter is None:
            raise ValueError('Hosted adapter required; no silent offline fallback')
        if self.budget.calls or self.budget.records:
            raise ValueError('Use a fresh budget for each run')
        self._used = True
        self.budget.started = time.monotonic()
        started_at = datetime.now(timezone.utc).isoformat()
        self.scenario, self.mode, self.version = scenario, mode, state_version
        self.messages, self.reasons, self.effects = [], [], []
        self.deferred, self.ignored, self.questions, self.proposals = set(), [], [], []
        self.challenges, self.raw_facts, self.history = [], None, []
        self.state = build_verified_state(scenario, [], state_version=state_version)
        candidate = validation = None
        try:
            if mode == 'multi':
                self._investigate()
                for spec in R.SPECIALISTS:
                    self._specialist(spec)
            else:
                self._single_analyse()
            candidate, validation = self._plan_and_review()
        except Exception as error:  # noqa: BLE001 - every failure becomes a visible escalation
            self.reasons.append(f'{type(error).__name__}: workflow stopped; inspect structured usage and evidence')
            self.message('coordinator', 'audit', {'error_type': type(error).__name__, 'detail': str(error)[:300]})
            candidate = validation = None
        questions = [*unresolved_questions(self.state), *self.questions]
        status = 'escalated' if self.reasons or candidate is None else 'awaiting_approval'
        if candidate is None and not self.reasons:
            self.reasons.append('No candidate plan was produced')
        result = RunResult(
            run_id=str(uuid4()), mode=mode, status=status, state=self.state, plan=candidate, validation=validation,
            messages=self.messages, model_usage=list(self.budget.records), reasons=self.reasons,
            metadata={'started_at_utc': started_at, 'duration_seconds': time.monotonic() - self.budget.started,
                      'protocol_version': R.PROTOCOL_VERSION, 'workflow': 'agent_orchestrator',
                      'agent_manifest': R.manifest(),
                      'auxiliary_requests': list(self.budget.auxiliary_records),
                      'raw_facts': self.raw_facts, 'final_facts': [f.model_dump() for f in self.state.facts],
                      'ignored_reports': [i.model_dump() for i in self.ignored],
                      'operator_questions': questions, 'priority_proposals': self.proposals,
                      'fact_challenges': self.challenges, 'decision_effects': self.effects,
                      'deferred_action_ids': sorted(self.deferred), 'input_hash': digest(scenario),
                      'planner': self.planner, 'reviewer_enabled': self.reviewer_enabled,
                      'feedback_enabled': self.feedback_enabled, 'raw_extraction_metrics': None,
                      'simulation_status': 'not_integrated',
                      'transport': 'injected_test_client' if self.adapter.injected_client else 'hosted',
                      'budget': {'max_calls': self.budget.max_calls, 'max_input_tokens': self.budget.max_input_tokens,
                                 'max_output_tokens': self.budget.max_output_tokens,
                                 'max_seconds': self.budget.max_seconds}})
        if self.trace_dir is not None:
            from .tracing import save_run
            save_run(result, self.trace_dir)
        return result

    # ------------------------------------------------------------------ helpers
    def message(self, sender, recipient, content):
        self.messages.append({'sender': sender, 'recipient': recipient, 'incident_id': self.scenario.scenario_id,
                              'state_version': self.version, 'finding': content})

    def allowed_evidence(self):
        return {r.report_id for r in self.scenario.reports} | {self.scenario.policy.evidence_id}

    def call(self, spec_role, stage, task, view, output, max_output, *, keep_history=False):
        self.budget.check_time()
        payload = {'stage': stage, 'task': task, 'state_version': self.version, 'context': view}
        role = 'single_agent' if self.mode == 'single' else spec_role
        result = self.adapter.complete(role, payload, output, max_output=max_output,
                                       evidence_ids=self.allowed_evidence(),
                                       history=self.history if self.mode == 'single' else None)
        if self.mode == 'single':
            self.history += [{'role': 'user', 'content': json.dumps(payload, separators=(',', ':'))},
                             {'role': 'assistant', 'content': result.model_dump_json()}]
        allowed = self.allowed_evidence()
        cited = set(getattr(result, 'evidence_ids', []) or [])
        for item in [*getattr(result, 'requests', []), *getattr(result, 'priority_proposals', [])]:
            cited |= set(item.evidence_ids)
        if not cited <= allowed:
            self.message('rejected_agent_output', 'audit', {'role': role, 'stage': stage,
                                                            'validation_error': 'cited nonexistent evidence'})
            raise ValueError('Agent cited nonexistent evidence')
        self.message(role, 'coordinator', {'stage': stage, **result.model_dump()})
        return result

    def apply_facts(self, facts, sender):
        accepted, rejected = normalize_facts(self.scenario, facts)
        for item in rejected:
            self.message('coordinator', sender, {'rejected_fact': item})
        self.state = build_verified_state(self.scenario, accepted, state_version=self.version)
        return accepted

    def apply_ignored(self, items):
        known = {r.report_id for r in self.scenario.reports}
        self.ignored = [i for i in items if i.report_id in known]

    def apply_requests(self, requests, sender):
        actions = {a.action_id for a in self.scenario.action_options}
        changed = False
        for request in requests:
            if not set(request.action_ids) <= actions or not request.reason.strip():
                self.message('coordinator', sender, {'rejected_request': request.model_dump(),
                                                     'reason': 'unknown action or empty reason'})
                continue
            added = set(request.action_ids) - self.deferred
            if not added:
                continue
            if not self.feedback_enabled:
                self.reasons.append('Agent requested action deferral; feedback disabled for ablation')
                return False
            self.deferred |= added
            self.version += 1
            self.state = build_verified_state(self.scenario, self.state.facts, state_version=self.version)
            effect = {'sender': sender, 'state_version': self.version, 'request': request.model_dump(),
                      'applied_action_ids': sorted(added), 'effect': 'excluded_from_candidate_schedule',
                      'operational_fact_verified': False}
            self.effects.append(effect)
            self.message('coordinator', 'deterministic_scheduler', effect)
            changed = True
        return changed

    def collect(self, result, sender):
        services = {s.service_id for s in self.scenario.services}
        for q in getattr(result, 'questions', []):
            self.questions.append({'source': sender, **q.model_dump()})
        for p in getattr(result, 'priority_proposals', []):
            if p.service_id in services:
                self.proposals.append({'source': sender, 'status': 'pending_human_decision', **p.model_dump()})

    # ------------------------------------------------------------------ multi
    def _investigate(self, challenges=None):
        view = R.investigator_view(self.scenario, {})
        if challenges:
            view['previous_facts'] = R.fact_rows(self.state.facts)
            view['reviewer_challenges'] = challenges
        out = self.call(R.INVESTIGATOR.role, 'investigate' if not challenges else 'reinvestigate',
                        R.INVESTIGATOR.task, view, R.Extraction, R.INVESTIGATOR.max_output)
        accepted = self.apply_facts(out.facts, R.INVESTIGATOR.role)
        if self.raw_facts is None:
            self.raw_facts = [f.model_dump() for f in accepted]
        self.apply_ignored(out.ignored_reports)
        for spec in (*R.SPECIALISTS, R.REVIEWER):
            self.message(R.INVESTIGATOR.role, spec.role, {'shared': 'facts', 'state_version': self.version,
                                                          'fact_count': len(accepted),
                                                          'ignored_report_ids': [i.report_id for i in self.ignored]})

    def _specialist(self, spec):
        ctx = {'state': self.state, 'ignored': self.ignored}
        out = self.call(spec.role, spec.stage, spec.task, spec.view(self.scenario, ctx), spec.output, spec.max_output)
        self.collect(out, spec.role)
        self.apply_requests(out.requests, spec.role)

    # ------------------------------------------------------------------ single
    def _single_analyse(self, challenges=None):
        ctx = {'state': self.state, 'ignored': []}
        view = R.single_view(self.scenario, ctx)
        if challenges:
            view = {'self_review_challenges': challenges, 'note': 'Re-extract with these corrections; repeat all other outputs.'}
        out = self.call('single_agent', 'analyse' if not challenges else 'reanalyse', R.SINGLE_ANALYSE_TASK, view,
                        R.SingleAnalysis, R.SINGLE_ANALYSE_MAX_OUTPUT)
        accepted = self.apply_facts(out.facts, 'single_agent')
        if self.raw_facts is None:
            self.raw_facts = [f.model_dump() for f in accepted]
        self.apply_ignored(out.ignored_reports)
        if not challenges:
            self.collect(out, 'single_agent')
        self.apply_requests(out.requests, 'single_agent')

    # ------------------------------------------------------------------ plan + review
    def _schedule(self):
        if self.planner == 'greedy':
            return greedy_plan(self.state, excluded_action_ids=self.deferred)
        return cp_sat_plan(self.state, solver_seconds=max(0.1, min(5, self.budget.remaining_seconds())),
                           excluded_action_ids=self.deferred)

    def _plan_and_review(self):
        if self.reasons:
            return None, None
        dirty, candidate, validation, nudge = True, None, None, None
        for revision in range(MAX_REVISIONS + 1):
            self.budget.check_time()
            if dirty:
                candidate = self._schedule()
                validation = validate(candidate, self.state)
                self.message('deterministic_scheduler', 'coordinator', candidate.model_dump())
                dirty = False
            if not validation.valid:
                self.reasons.append('Independent validation failed')
                return candidate, validation
            if not self.reviewer_enabled:
                return candidate, validation
            ctx = {'state': self.state, 'ignored': self.ignored, 'plan_view': plan_view(candidate),
                   'validation': validation.model_dump(), 'arithmetic': arithmetic_checks(candidate, self.scenario),
                   'forecast': service_forecast(self.state, candidate), 'deferred': self.deferred}
            view = R.reviewer_view(self.scenario, ctx)
            if self.mode == 'single':
                # The single agent already holds the reports, directory and rules in its
                # own conversation; resend only what is new.
                view = {k: v for k, v in view.items() if k not in ('reports', 'site_directory', 'rules')}
            if nudge:
                view['coordinator_note'] = nudge
            review = self.call(R.REVIEWER.role, 'review', R.REVIEWER.task, view, R.PlanReview, R.REVIEWER.max_output)
            reports = {r.report_id for r in self.scenario.reports}
            challenges = [c.model_dump() for c in review.fact_challenges if c.report_id in reports]
            new_holds = [r for r in review.requests if set(r.action_ids) - self.deferred]
            if review.decision == 'escalate':
                self.reasons.extend(review.findings or ['Reviewer escalated without findings'])
                return candidate, validation
            if review.decision == 'approve' and not challenges and not new_holds:
                return candidate, validation
            if revision == MAX_REVISIONS:
                self.reasons.append('Review did not approve within revision budget')
                return candidate, validation
            if not self.feedback_enabled:
                self.reasons.append('Review requested revision; feedback disabled for ablation')
                return candidate, validation
            nudge = None
            if challenges:
                self.challenges.extend({'round': revision + 1, **c} for c in challenges)
                target = 'network_investigator' if self.mode == 'multi' else 'single_agent'
                self.message(R.REVIEWER.role if self.mode == 'multi' else 'single_agent', target,
                             {'fact_challenges': challenges, 'routed_by': 'coordinator'})
                self.version += 1
                if self.mode == 'multi':
                    self._investigate(challenges)
                else:
                    self._single_analyse(challenges)
                dirty = True
            if new_holds:
                dirty = self.apply_requests(new_holds, R.REVIEWER.role if self.mode == 'multi' else 'single_agent') or dirty
                if self.reasons:
                    return candidate, validation
            if not dirty:
                nudge = ('Your revise decision changed nothing. Give a concrete fact_challenge or a NEW defer_action, '
                         'otherwise approve the unchanged plan or escalate if it is unsafe.')
        return candidate, validation
