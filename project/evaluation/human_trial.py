"""Score human participants' schedules with the same validator and simulator as the AI.

A participant reads an incident in the dashboard (signed in as Auditor: no AI, no
optimiser) and records, per crew, the ordered action IDs they would dispatch.
This tool turns that order into clock times (departure when the crew is free,
travel by the shortest open road, work for the catalogue duration), drops and
records any action that cannot be scheduled, validates the result, approves it
as an automated operator and simulates the whole incident against hidden truth.

Usage:
    python -m project.evaluation.human_trial --submissions docs/human_baseline/submissions/*.json \
        --data-root releases/evidence-v3-20261126/data --output results/human_baseline/run1

The evidence state used for checking is built from the cases' authoritative
report labels (what a careful reader should conclude). Participants never see
these labels.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

import networkx as nx

from project.core.coordinator import approve
from project.core.planner import _route
from project.core.schemas import EvidenceFact, Plan, ScheduledAction
from project.core.state import build_verified_state, digest
from project.core.validator import action_needed, road_graph, validate
from project.data.evaluator import EvaluatorLoader
from project.data.loader import CaseLoader
from project.simulation.episode import IncidentEpisode

HUMAN_CASES = ('DEMO-005', 'DEV-001', 'DEV-002', 'DEV-003', 'DEV-004', 'DEV-005')
MAX_MINUTES_PER_CASE = 10


def reference_state(case, truth):
    reports = {r.report_id: r for r in case.reports}
    facts = [EvidenceFact(target_type=l['target_type'], target_id=l['target_id'], attribute=l['attribute'],
                          value=l['reported_value'], evidence_ids=[l['report_id']],
                          observed_at_min=reports[l['report_id']].observed_at_min,
                          received_at_min=reports[l['report_id']].received_at_min,
                          status='verified' if reports[l['report_id']].source_type in
                          {'authoritative_snapshot', 'operator_confirmation', 'confirmed_field_update'} else 'unverified')
             for l in truth.expected_report_facts]
    return build_verified_state(case, facts)


def build_human_plan(state, assignments):
    """assignments: {crew_id: [action_id, ...]} in the participant's order."""
    s = state.scenario
    graph = road_graph(state)
    options = {o.action_id: o for o in s.action_options}
    crews = {c.crew_id: c for c in s.crews}
    gens = {g.generator_id: g for g in s.generators}
    actions, rejected, used = [], [], set()
    generator_used = False
    for crew_id, order in assignments.items():
        crew = crews.get(crew_id)
        if crew is None:
            rejected.extend({'action_id': a, 'crew_id': crew_id, 'reason': 'unknown crew'} for a in order)
            continue
        location, ready = crew.location, max(s.current_time_min, crew.available_from_min)
        for action_id in order:
            o = options.get(action_id)
            reason = None
            if o is None:
                reason = 'unknown action'
            elif action_id in used:
                reason = 'already assigned'
            elif o.required_skill not in crew.skills:
                reason = 'crew lacks skill'
            elif not action_needed(state, o):
                reason = 'not needed or fault not established by the reports'
            elif o.kind == 'generator_deploy' and (generator_used or not gens[o.generator_id].available):
                reason = 'generator unavailable or already deployed'
            if reason is None:
                try:
                    route, travel = _route(graph, location, o, gens)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    reason = 'no open road'
            if reason is None:
                start = ready + travel
                end = start + o.duration_minutes
                if end > min(s.horizon_min, crew.available_until_min):
                    reason = 'does not finish inside the crew window'
            if reason:
                rejected.append({'action_id': action_id, 'crew_id': crew_id, 'reason': reason})
                continue
            actions.append(ScheduledAction(action_id=o.action_id, kind=o.kind, target_id=o.target_id, crew_id=crew_id,
                                           generator_id=o.generator_id, departure_min=ready, travel_route=route,
                                           work_start_min=start, work_end_min=end))
            used.add(action_id)
            generator_used |= o.kind == 'generator_deploy'
            location, ready = o.location, end
    plan = Plan(plan_id=str(uuid4()), scenario_id=s.scenario_id, state_version=state.state_version,
                state_hash=digest(state), actions=actions, unmet_needs=[], evidence_ids=[s.policy.evidence_id],
                planner_config={'algorithm': 'human_order_timed_by_tool'}, explanation='Human participant schedule')
    return plan, rejected


def score_case(case, truth, assignments):
    state = reference_state(case, truth)
    plan, rejected = build_human_plan(state, assignments)
    validation = validate(plan, state)
    row = {'scenario_id': case.scenario_id, 'actions_submitted': sum(len(v) for v in assignments.values()),
           'actions_scheduled': len(plan.actions), 'actions_rejected': rejected, 'plan_valid': validation.valid}
    if not validation.valid:
        row['violations'] = [v.model_dump() for v in validation.violations]
        return row
    approval = approve(plan.plan_id, state.state_version, 'approve', plan=plan, state=state,
                       operator_id='Human-trial scorer (automated)')
    episode = IncidentEpisode(case, truth)
    result = episode.advance(case, plan, approval, state=state)
    metrics = result['metrics'] if isinstance(result, dict) else result.metrics
    if not episode.complete:
        row['note'] = 'Case has a mid-incident event; not used for the human baseline'
        return row
    row.update(weighted_downtime=metrics['weighted_downtime_min'],
               critical_service_downtime=metrics.get('critical_service_downtime_min'),
               scored=True)
    return row


def score_submission(path, data_root):
    data = json.loads(Path(path).read_text())
    loader = CaseLoader(Path(data_root) / 'processed' / 'agent_inputs')
    truths = EvaluatorLoader(Path(data_root) / 'evaluation' / 'ground_truth')
    rows = []
    for entry in data['cases']:
        case = loader.load_case(loader.find(entry['scenario_id']))
        row = score_case(case, truths.load(case.scenario_id), entry['assignments'])
        minutes = entry.get('minutes_spent')
        row.update(participant=data['participant_id'], expertise=data.get('expertise', 'not stated'),
                   order_position=entry.get('order_position'), minutes_spent=minutes,
                   within_time_limit=minutes is not None and minutes <= MAX_MINUTES_PER_CASE)
        rows.append(row)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--submissions', nargs='+', required=True, type=Path)
    parser.add_argument('--data-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    rows = [row for path in args.submissions for row in score_submission(path, args.data_root)]
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'human_rows.json').write_text(json.dumps(rows, indent=2))
    scored = [r for r in rows if r.get('scored')]
    summary = {'participants': len({r['participant'] for r in rows}), 'case_attempts': len(rows),
               'scored': len(scored), 'invalid_plans': sum(not r['plan_valid'] for r in rows),
               'median_minutes': sorted(r['minutes_spent'] for r in rows if r['minutes_spent'] is not None)[len(rows) // 2]
               if rows else None,
               'note': 'Exploratory human baseline; small sample. Same validator and simulator as AI runs.'}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))
    return 0


if __name__ == '__main__':
    sys.exit(main())
