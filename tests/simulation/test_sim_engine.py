"""Numerical five-site example, dependencies, expiry, boundaries and failures."""

import pytest

from project.core.state import digest
from project.data.evaluator import FutureEvent, OperatorReport, TruthPatch
from project.simulation.engine import SimulationRejected, TopologyError, evaluate_services, simulate
from sim_helpers import GEN_S02, act, make_approval, make_plan, run


def avail(result, sid):
    return result.run_metadata['service_availability'][sid]['intervals']


def test_initial_demo_availability_is_zero(demo, truth):
    r = run(demo, truth, [])
    assert r.metrics['weighted_available_min'] == 0
    assert r.metrics['services_available_at_horizon_end'] == 0
    assert r.metrics['first_restoration_min'] is None
    assert r.trajectory[0]['type'] == 'availability' and r.trajectory[0]['available_services'] == []
    assert r.metrics['weighted_downtime_min'] == 9 * 720


def test_generator_at_s02_restores_s02_and_s04_with_weight_six(demo, truth):
    r = run(demo, truth, [GEN_S02()])
    assert avail(r, 'V02') == [[30, 150]] and avail(r, 'V04') == [[30, 150]]
    for sid in ('V01', 'V03', 'V05'):
        assert avail(r, sid) == []          # the S01 branch stays down
    snap = [e for e in r.trajectory if e['type'] == 'availability' and e['t'] == 30][0]
    assert snap['available_services'] == ['V02', 'V04'] and snap['weighted_available'] == 6
    m = r.metrics
    assert m['weighted_available_min'] == 6 * 120
    assert m['total_weighted_horizon_min'] == 9 * 720
    assert m['weighted_downtime_min'] == 9 * 720 - 720 == 5760
    assert m['first_restoration_min'] == 30
    assert m['critical_service_downtime_min'] == 720 - 120
    assert m['unweighted_availability'] == pytest.approx(240 / 3600)
    assert m['services_available_at_horizon_end'] == 0 and m['unmet_needs_count'] == 5
    assert m['weighted_downtime_reduction_min'] == 720
    assert r.completed_actions == ['GEN-G1-S02']
    assert r.unmet_needs == [f'service:V0{i}' for i in range(1, 6)]


def test_expiry_removes_service_and_uses_truth_autonomy(demo, truth):
    t = truth.model_copy(deep=True)
    t.generators[0].autonomy_minutes = 60       # evaluator truth differs from visible 120
    r = run(demo, t, [GEN_S02()])
    assert avail(r, 'V02') == [[30, 90]]
    assert any(e['type'] == 'generator_expired' and e['t'] == 90 for e in r.trajectory)
    assert r.metrics['weighted_available_min'] == 6 * 60


def test_half_open_interval_boundaries(demo, truth):
    r = run(demo, truth, [GEN_S02()])
    at = {e['t']: e['available_services'] for e in r.trajectory if e['type'] == 'availability'}
    assert at[0] == [] and at[30] == ['V02', 'V04']      # available at completion minute
    assert at[150] == []                                  # not available at expiry minute
    assert 149 not in at and 29 not in at


def test_link_repair_alone_does_not_restore_unpowered_branch(demo, truth):
    r = run(demo, truth, [act('BH-L01', 'link_repair', 'L01', 'C2', ['DEPOT', 'S01'], 0, 25, 115)])
    assert r.completed_actions == ['BH-L01']
    assert r.metrics['weighted_available_min'] == 0
    assert r.metrics['first_restoration_min'] is None


def test_simultaneous_completion_and_generator_power_on_s01_branch(demo, truth):
    # Link repair completes at 115 and the generator deployment completes at 115.
    link = act('BH-L01', 'link_repair', 'L01', 'C2', ['DEPOT', 'S01'], 0, 25, 115)
    gen = act('GEN-G1-S01', 'generator_deploy', 'S01', 'C1', ['DEPOT', 'S01'], 75, 100, 115, 'G1')
    r = run(demo, truth, [gen, link])
    for sid in ('V01', 'V03', 'V05'):
        assert avail(r, sid) == [[115, 235]]
    assert avail(r, 'V02') == [] and avail(r, 'V04') == []
    assert r.metrics['first_restoration_min'] == 115
    assert r.metrics['weighted_available_min'] == 3 * 120
    assert sorted(r.completed_actions) == ['BH-L01', 'GEN-G1-S01']


def test_services_counted_once_when_sites_share_paths():
    parents = {'S1': ('CORE', 'L1'), 'S2': ('S1', 'L2')}

    class S:  # two services at S2, one at S1
        def __init__(self, sid, site): self.service_id, self.site_id = sid, site
    svc = [S('A', 'S1'), S('B', 'S2'), S('C', 'S2')]
    up = evaluate_services(parents, 'CORE', svc, {'S1': True, 'S2': True}, {'S1', 'S2'}, {'L1': True, 'L2': True})
    assert up == frozenset({'A', 'B', 'C'})
    down = evaluate_services(parents, 'CORE', svc, {'S1': True, 'S2': True}, {'S2'}, {'L1': True, 'L2': True})
    assert down == frozenset()           # downstream is not counted when the upstream is unpowered


def test_cycle_and_disconnected_topology_rejected():
    class S:
        service_id, site_id = 'A', 'S1'
    flags = ({'S1': True, 'S2': True}, {'S1', 'S2'}, {'L1': True, 'L2': True})
    with pytest.raises(TopologyError):
        evaluate_services({'S1': ('S2', 'L1'), 'S2': ('S1', 'L2')}, 'CORE', [S()], *flags)
    with pytest.raises(TopologyError):
        evaluate_services({'S2': ('CORE', 'L2')}, 'CORE', [S()], *flags)


# ---- approval and plan rejection -------------------------------------------------
def test_reject_decision_and_mismatches(demo, truth):
    plan = make_plan([GEN_S02()])
    ok = make_approval(plan)
    with pytest.raises(SimulationRejected, match='not approve'):
        simulate(demo, plan, make_approval(plan, 'reject'), truth)
    with pytest.raises(SimulationRejected, match='plan ID or state version'):
        simulate(demo, plan, ok.model_copy(update={'plan_id': 'OTHER'}), truth)
    with pytest.raises(SimulationRejected, match='plan ID or state version'):
        simulate(demo, plan, ok.model_copy(update={'state_version': 2}), truth)
    with pytest.raises(SimulationRejected, match='state hash'):
        simulate(demo, plan, ok.model_copy(update={'state_hash': 'x'}), truth)


def test_plan_changed_after_approval_is_rejected(demo, truth):
    plan = make_plan([GEN_S02()])
    approval = make_approval(plan)
    tampered = plan.model_copy(update={'actions': [act('GEN-G1-S01', 'generator_deploy', 'S01', 'C1',
                                                       ['DEPOT', 'S01'], 0, 25, 40, 'G1')]})
    with pytest.raises(SimulationRejected, match='changed after approval'):
        simulate(demo, tampered, approval, truth)


def test_state_version_change_invalidates_approval(demo, truth):
    plan = make_plan([GEN_S02()])
    approval = make_approval(plan)
    newer = make_plan([GEN_S02()], version=2)       # a new state version needs a new approval
    with pytest.raises(SimulationRejected):
        simulate(demo, newer, approval, truth)


def test_scenario_and_truth_must_match(demo, truth):
    plan = make_plan([GEN_S02()])
    with pytest.raises(SimulationRejected, match='different scenario'):
        simulate(demo.model_copy(update={'scenario_id': 'OTHER'}), plan, make_approval(plan), truth)
    bad = truth.model_copy(update={'scenario_id': 'OTHER'})
    with pytest.raises(SimulationRejected, match='Truth belongs'):
        simulate(demo, plan, make_approval(plan), bad)


@pytest.mark.parametrize('mutation, message', [
    (lambda a: a.model_copy(update={'work_end_min': 35}), 'wrong work duration'),
    (lambda a: a.model_copy(update={'work_start_min': 10, 'work_end_min': 25}), 'before arrival'),
    (lambda a: a.model_copy(update={'travel_route': ['DEPOT', 'S03', 'S02']}), 'route'),
    (lambda a: a.model_copy(update={'action_id': 'NOPE'}), 'unknown action'),
    (lambda a: a.model_copy(update={'crew_id': 'C9'}), 'unknown action or crew'),
    (lambda a: a.model_copy(update={'departure_min': 0, 'travel_route': ['DEPOT', 'S01']}), 'route'),
])
def test_structurally_invalid_plans_rejected(demo, truth, mutation, message):
    with pytest.raises(SimulationRejected, match=message):
        run(demo, truth, [mutation(GEN_S02())])


def test_duplicate_overlap_and_second_generator_rejected(demo, truth):
    g2 = act('GEN-G1-S01', 'generator_deploy', 'S01', 'C2', ['DEPOT', 'S01'], 0, 25, 40, 'G1')
    with pytest.raises(SimulationRejected, match='More than one generator'):
        run(demo, truth, [GEN_S02(), g2])
    with pytest.raises(SimulationRejected, match='Duplicate action'):
        run(demo, truth, [GEN_S02(), GEN_S02()])
    eq = act('EQ-S02', 'equipment_repair', 'S02', 'C1', ['S02'], 20, 20, 80)
    with pytest.raises(SimulationRejected, match='overlaps previous'):
        run(demo, truth, [GEN_S02(), eq])


# ---- truth-dependent execution ----------------------------------------------------
def test_closed_road_in_truth_fails_action_and_blocks_crew(demo, truth):
    t = truth.model_copy(deep=True)
    t.roads['R02'] = False
    r = run(demo, t, [GEN_S02()])
    assert r.completed_actions == []
    assert r.run_metadata['action_outcomes']['GEN-G1-S02']['status'] == 'failed'
    assert r.metrics['weighted_available_min'] == 0


def test_equipment_repair_changes_state_only_when_truth_faulty(demo, truth):
    t = truth.model_copy(deep=True)
    t.sites['S02'].equipment_ok = False
    gen = GEN_S02('C2')
    eq = act('EQ-S02', 'equipment_repair', 'S02', 'C1', ['DEPOT', 'S02'], 0, 15, 75)
    r = run(demo, t, [gen, eq])
    # powered from 30, equipment fixed at 75: services come up only then
    assert avail(r, 'V02') == [[75, 150]] and avail(r, 'V04') == [[75, 150]]


def test_inputs_not_mutated_and_run_is_deterministic(demo, truth):
    plan = make_plan([GEN_S02()])
    approval = make_approval(plan)
    before = (digest(demo), digest(plan), truth.model_dump_json())
    a = simulate(demo, plan, approval, truth)
    b = simulate(demo, plan, approval, truth)
    assert (digest(demo), digest(plan), truth.model_dump_json()) == before
    assert a.model_dump() == b.model_dump()
    assert a.run_metadata['planner_prediction_used'] is False


# ---- future event (crew loss) ------------------------------------------------------
def crew_loss(truth, at=60, until=60):
    t = truth.model_copy(deep=True)
    t.future_events = [FutureEvent(
        event_id='EVT-T', at_min=at,
        operator_report=OperatorReport(report_id='EVENT-REP-T', source_type='confirmed_field_update',
                                       observed_at_min=at, text='Crew C2 is unavailable for the rest of the incident.'),
        truth_patch=TruthPatch(crew_id='C2', available_until_min=until))]
    return t


def test_crew_loss_pauses_unfinished_work_keeps_completed_and_requests_replan(demo, truth):
    t = crew_loss(truth)
    first = GEN_S02('C2')                                                    # completes at 30
    second = act('BH-L02', 'link_repair', 'L02', 'C2', ['S02'], 30, 30, 150)   # unfinished at 60
    r = run(demo, t, [first, second])
    outcomes = r.run_metadata['action_outcomes']
    assert outcomes['GEN-G1-S02']['status'] == 'completed' and outcomes['BH-L02']['status'] == 'paused'
    assert r.completed_actions == ['GEN-G1-S02']
    assert avail(r, 'V02') == [[30, 60]]                      # prefix stops at event; future fuel is not scored
    assert r.metrics['services_available_at_horizon_end'] is None
    assert r.run_metadata['replan_required'] is True
    obs = [e for e in r.trajectory if e['type'] == 'observation']
    assert len(obs) == 1 and obs[0]['t'] == 60 and obs[0]['replan_required'] is True
    assert all(e['t'] >= 60 for e in r.trajectory if e['type'] in ('observation', 'action_paused'))


def test_action_ending_exactly_at_loss_minute_completes(demo, truth):
    t = crew_loss(truth, at=30, until=30)
    r = run(demo, t, [GEN_S02('C2')])
    assert r.run_metadata['action_outcomes']['GEN-G1-S02']['status'] == 'completed'


def test_no_event_means_no_replan_flag(demo, truth):
    assert run(demo, truth, [GEN_S02()]).run_metadata['replan_required'] is False
