"""Human-baseline scorer uses the same validator and simulator as AI runs."""
import json
from pathlib import Path

from project.core.planner import plan as cp_sat_plan
from project.data.evaluator import EvaluatorLoader
from project.data.loader import CaseLoader
from project.evaluation import human_trial as H

V3 = Path(__file__).resolve().parents[2] / 'releases' / 'evidence-v3-20261126' / 'data'
LOADER = CaseLoader(V3 / 'processed' / 'agent_inputs')
TRUTH = EvaluatorLoader(V3 / 'evaluation' / 'ground_truth')


def test_human_cases_exist_and_have_no_mid_incident_events():
    for cid in H.HUMAN_CASES:
        assert not TRUTH.load(cid).future_events
        LOADER.load_case(LOADER.find(cid))


def test_optimizer_order_entered_by_hand_scores_like_the_optimizer():
    case = LOADER.load_case(LOADER.find('DEV-003'))
    truth = TRUTH.load('DEV-003')
    state = H.reference_state(case, truth)
    reference = cp_sat_plan(state)
    order = {}
    for action in sorted(reference.actions, key=lambda a: a.work_start_min):
        order.setdefault(action.crew_id, []).append(action.action_id)
    row = H.score_case(case, truth, order)
    assert row['scored'] and row['plan_valid'] and not row['actions_rejected']
    assert row['actions_scheduled'] == len(reference.actions)


def test_infeasible_choices_are_dropped_and_recorded():
    case = LOADER.load_case(LOADER.find('DEV-003'))
    truth = TRUTH.load('DEV-003')
    crew = case.crews[0].crew_id
    unneeded = next(o.action_id for o in case.action_options if o.kind == 'equipment_repair')
    row = H.score_case(case, truth, {crew: ['NOT-AN-ACTION', unneeded], 'C99': ['X']})
    reasons = {r['reason'] for r in row['actions_rejected']}
    assert {'unknown action', 'unknown crew'} <= reasons and row['plan_valid']


def test_cli_scores_a_submission(tmp_path):
    submission = {'participant_id': 'TEST-ONLY', 'expertise': 'synthetic test', 'cases': [
        {'scenario_id': 'DEV-001', 'order_position': 1, 'minutes_spent': 4,
         'assignments': {'C2': ['EQ-S01']}}]}
    path = tmp_path / 'p.json'
    path.write_text(json.dumps(submission))
    assert H.main(['--submissions', str(path), '--data-root', str(V3), '--output', str(tmp_path / 'out')]) == 0
    rows = json.loads((tmp_path / 'out' / 'human_rows.json').read_text())
    assert rows[0]['participant'] == 'TEST-ONLY' and rows[0]['within_time_limit']
