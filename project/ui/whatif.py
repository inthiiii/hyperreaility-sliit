"""What-if sandbox: take a crew away or close a road, replan and compare.

Everything runs on copies. The session's plan, approval and results are never
changed, no model is called (replanning is CP-SAT on the facts the agents already
established), and hidden truth is used only inside separate what-if simulations,
exactly like the no-AI comparison.
"""
from __future__ import annotations

from pathlib import Path

from project.core.coordinator import approve
from project.core.planner import plan as cp_sat_plan
from project.core.schemas import ScenarioInput
from project.core.state import build_verified_state, digest
from project.core.validator import validate

OPERATOR = 'What-if sandbox (automated, not an operational approval)'


def has_truth(choice):
    """Only approved dataset inputs have an evaluator answer; uploads do not."""
    return choice.key.startswith(('releases/', 'data/processed/'))


def _state(scenario, facts, version):
    try:
        return build_verified_state(scenario, facts, state_version=version)
    except ValueError:
        return build_verified_state(scenario, [], state_version=version)


def disrupt(state, crews_out=None, roads_closed=(), truth=None):
    """(disrupted VerifiedState, disrupted truth or None). ``crews_out`` maps crew -> unavailable-until minute."""
    crews_out = dict(crews_out or {})
    data = state.scenario.model_dump(mode='python')
    horizon = data['horizon_min']

    def shift(crew):
        if crew['crew_id'] in crews_out:
            start = min(max(crew['available_from_min'], int(crews_out[crew['crew_id']])), horizon - 1)
            crew['available_from_min'] = start
            crew['available_until_min'] = max(crew['available_until_min'], start + 1)

    for crew in data['crews']:
        shift(crew)
    for road in roads_closed:
        if road in data['observed_state']['roads']:
            data['observed_state']['roads'][road] = False
    scenario = ScenarioInput.model_validate(data)
    new_state = _state(scenario, state.facts, state.state_version)
    for road in roads_closed:
        if road in new_state.resolved_observations.roads:
            new_state.resolved_observations.roads[road] = False
    new_truth = None
    if truth is not None:
        t = truth.model_dump(mode='python')
        for crew in t['crews']:
            shift(crew)
        for road in roads_closed:
            if road in t['roads']:
                t['roads'][road] = False
        new_truth = type(truth).model_validate(t)
    return new_state, new_truth


def rebind(plan, state):
    """The same jobs, checked against another state (for 'would my plan still work?')."""
    return plan.model_copy(update={'state_hash': digest(state), 'state_version': state.state_version,
                                   'scenario_id': state.scenario_id})


def simulate(state, plan, truth, max_episodes=10):
    """Measure one plan in a fresh simulator episode; later events are replanned with CP-SAT."""
    from project.simulation.episode import IncidentEpisode
    episode = IncidentEpisode(state.scenario, truth)
    events = 0
    for _ in range(max_episodes):
        approval = approve(plan.plan_id, state.state_version, 'approve', plan=plan, state=state, operator_id=OPERATOR)
        sim = episode.advance(state.scenario, plan, approval, state=state)
        if episode.complete:
            m = sim.metrics
            return {'weighted_downtime_min': m['weighted_downtime_min'],
                    'critical_service_downtime_min': m.get('critical_service_downtime_min'),
                    'services_up_at_end': m.get('services_available_at_horizon_end'),
                    'replanned_after_events': events}
        events += 1
        state = _state(episode.checkpoint(), state.facts, state.state_version + 1)
        plan = cp_sat_plan(state)
    raise ValueError('Incident did not complete within the episode limit')


def _problems(check):
    return [f'{v.action_id}: {v.reason}' if v.action_id else v.reason for v in check.violations]


def jobs(plan):
    return {(a.crew_id, a.action_id) for a in (plan.actions if plan else [])}


def compare(result, crews_out, roads_closed, truth=None, solver_seconds=5):
    """Rows for: current plan as is, current plan under disruption, replanned under disruption."""
    state, plan = result.state, result.plan
    world, world_truth = disrupt(state, crews_out, roads_closed, truth)
    replan = cp_sat_plan(world, solver_seconds=solver_seconds)
    replan_check = validate(replan, world)
    kept = rebind(plan, world)
    kept_check = validate(kept, world)
    rows = [{'Option': 'Current plan · normal conditions', 'plan': plan, 'valid': True, 'problems': []},
            {'Option': 'Current plan · with the disruption', 'plan': kept, 'valid': kept_check.valid,
             'problems': _problems(kept_check)},
            {'Option': 'Replanned for the disruption', 'plan': replan, 'valid': replan_check.valid,
             'problems': _problems(replan_check)}]
    if truth is not None:
        for row, (s, t) in zip(rows, ((state, truth), (world, world_truth), (world, world_truth))):
            if row['valid']:
                try:
                    row['measured'] = simulate(s, row['plan'], t)
                except Exception as error:  # noqa: BLE001 - shown to the user
                    row['measured'] = {'error': f'{type(error).__name__}: {error}'[:200]}
    before, after = jobs(plan), jobs(replan)
    return {'rows': rows, 'added': sorted(after - before), 'dropped': sorted(before - after), 'world': world}


def load_truth(root, choice):
    from project.data.evaluator import EvaluatorLoader
    data_root = (Path(root).resolve() / choice.key).parents[3]
    return EvaluatorLoader(data_root / 'evaluation' / 'ground_truth').load(choice.scenario.scenario_id)
