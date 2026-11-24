from project.core.schemas import Approval, Plan, ScheduledAction
from project.core.state import digest

STATE_HASH = 'test-state-hash'


def act(action_id, kind, target, crew, route, departure, start, end, generator=None):
    return ScheduledAction(action_id=action_id, kind=kind, target_id=target, crew_id=crew,
                           generator_id=generator, departure_min=departure, travel_route=route,
                           work_start_min=start, work_end_min=end)


def GEN_S02(crew='C1'):
    return act('GEN-G1-S02', 'generator_deploy', 'S02', crew, ['DEPOT', 'S02'], 0, 15, 30, 'G1')


def make_plan(actions, version=1, plan_id='PLAN-T1'):
    return Plan(plan_id=plan_id, scenario_id='DEMO-005', state_version=version, state_hash=STATE_HASH,
                actions=actions, unmet_needs=[], evidence_ids=[], planner_config={})


def make_approval(plan, decision='approve'):
    return Approval(plan_id=plan.plan_id, plan_hash=digest(plan), state_version=plan.state_version,
                    state_hash=plan.state_hash, decision=decision, operator_id='test-operator')


def run(demo, truth, actions, **kw):
    import copy
    from project.simulation.engine import simulate
    plan = make_plan(actions)
    return simulate(copy.deepcopy(demo), plan, make_approval(plan), truth, **kw)
