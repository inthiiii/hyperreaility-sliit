"""Independent numerical and lifecycle acceptance tests for incident checkpoints."""
import copy
import pytest
from project.core.coordinator import Coordinator
from project.core.integration import CoreSession
from project.core.schemas import Report
from project.core.state import digest
from project.data.evaluator import EvaluatorLoader, FutureEvent, OperatorReport, TruthPatch
from project.data.loader import load_case
from project.simulation.engine import simulate, SimulationRejected
from project.simulation.episode import IncidentEpisode
from sim_helpers import GEN_S02, make_plan, make_approval


def event(crew='C2', at=60, name='LOSS'):
    return FutureEvent(event_id=name, at_min=at,
        operator_report=OperatorReport(report_id=name+'-REP', source_type='confirmed_field_update',
            observed_at_min=at, text=f'Crew {crew} unavailable from minute {at}.'),
        truth_patch=TruthPatch(crew_id=crew, available_until_min=at))


def prepared(episode, scenario, core):
    run = core.prepare(Coordinator(), scenario, 'template')
    assert run.status == 'awaiting_approval', run.reasons
    approval = core.approve('Acceptance operator')
    result = episode.advance(scenario, run.plan, approval, state=run.state)
    return result, run, approval


def test_real_case_continues_to_720_with_completed_work_and_original_expiry():
    scenario = load_case('development/DEV-010.json')
    truth = EvaluatorLoader().load('DEV-010')
    episode = IncidentEpisode(scenario, truth); core = CoreSession()
    first, run1, approval1 = prepared(episode, scenario, core)
    assert episode.paused and not episode.complete
    assert first.metrics['observed_until_min'] == 60
    assert first.metrics['weighted_downtime_min'] is None
    assert first.metrics['weighted_downtime_so_far_min'] >= 0
    assert all(row['t'] <= 60 for row in first.trajectory)
    checkpoint = episode.checkpoint()
    assert checkpoint.current_time_min == 60 and checkpoint.horizon_min == 720
    active = checkpoint.active_generators[0]
    assert active.expires_at_min == 145  # Started at 25, autonomy 120; never refuelled on resume.
    c1 = next(c for c in checkpoint.crews if c.crew_id == 'C1')
    assert c1.location == 'S01' and c1.available_from_min == 145
    assert 'EQ-S01' not in {a.action_id for a in checkpoint.action_options}  # already committed
    before = digest(checkpoint)
    with pytest.raises(SimulationRejected):
        episode.advance(checkpoint, run1.plan, approval1, state=run1.state)
    assert digest(episode.checkpoint()) == before
    final, run2, _ = prepared(episode, checkpoint, core)
    assert run2.state.state_version > run1.state.state_version
    assert episode.complete and not episode.paused
    assert final.metrics['horizon_min'] == final.metrics['measured_duration_min'] == 720
    # Independent arithmetic: 13 weighted services on S02 branch for [25,145),
    # 10 on S01 branch for [145,720). Full policy weight is 23.
    assert final.metrics['weighted_available_min'] == 13 * 120 + 10 * 575 == 7310
    assert final.metrics['weighted_downtime_min'] == 23 * 720 - 7310 == 9250
    assert final.metrics['services_available_at_horizon_end'] == 10
    assert sum(row['type']=='action_completed' and row['action_id']=='EQ-S01' for row in final.trajectory) == 1
    with pytest.raises(SimulationRejected): episode.advance(checkpoint, run2.plan, core.approval, state=run2.state)


def test_prefix_and_resumed_generator_intervals_equal_uninterrupted_oracle(demo, truth):
    truth = truth.model_copy(deep=True); truth.future_events = [event()]
    episode = IncidentEpisode(demo, truth)
    initial = make_plan([GEN_S02()]); approval = make_approval(initial)
    first = episode.advance(demo, initial, approval)
    assert first.metrics['weighted_available_so_far_min'] == 6 * 30
    assert first.run_metadata['service_availability']['V02']['intervals'] == [[30, 60]]
    checkpoint = episode.checkpoint()
    # Resolve only original visible reports; no evaluator answers are injected.
    core = CoreSession(); core._next_state_version = 2
    final, _, _ = prepared(episode, checkpoint, core)
    assert final.metrics['weighted_available_min'] == 720
    assert final.metrics['weighted_downtime_min'] == 5760
    assert final.metrics['unweighted_available_min'] == 240
    assert final.metrics['unweighted_downtime_min'] == 3360
    assert final.run_metadata['service_availability']['V02']['intervals'] == [[30, 150]]


def test_horizon_expiry_applies_after_last_scored_interval(demo, truth):
    scenario = demo.model_copy(update={'horizon_min':150})
    p = make_plan([GEN_S02()])
    result = simulate(scenario, p, make_approval(p), truth)
    assert result.metrics['weighted_available_min'] == 720
    assert result.metrics['services_available_at_horizon_end'] == 0
    assert result.metrics['unmet_needs_count'] == 5
    assert all(row['t'] <= 150 for row in result.trajectory)


def test_work_completion_at_horizon_updates_end_state_without_adding_minutes(demo, truth):
    s = demo.model_copy(update={'horizon_min':30})
    p = make_plan([GEN_S02()])
    r = simulate(s,p,make_approval(p),truth)
    assert r.metrics['weighted_available_min'] == 0
    assert r.metrics['services_available_at_horizon_end'] == 2


def test_later_hidden_event_is_not_in_first_snapshot_or_result(demo, truth):
    t = truth.model_copy(deep=True);t.future_events = [event(at=60),event(crew='C1',at=120,name='SECRET-LATER')]
    episode = IncidentEpisode(demo,t)
    first, _, _ = prepared(episode,demo,CoreSession())
    assert 'SECRET-LATER' not in first.model_dump_json() + episode.checkpoint().model_dump_json()
    core = CoreSession();core._next_state_version=2
    second, _, _ = prepared(episode,episode.checkpoint(),core)
    assert second.metrics['observed_until_min'] == 120 and episode.paused
    third, _, _ = prepared(episode,episode.checkpoint(),core)
    assert third.metrics['observed_until_min'] == 720 and episode.complete


def test_invalid_truth_event_is_rejected_before_any_simulation(demo,truth):
    t = truth.model_copy(deep=True);t.future_events=[event(),event()]
    with pytest.raises(SimulationRejected,match='Duplicate'):IncidentEpisode(demo,t)


def test_failed_validation_does_not_advance_checkpoint(demo,truth):
    t=truth.model_copy(deep=True);t.future_events=[event()]
    episode=IncidentEpisode(demo,t);core=CoreSession()
    _,run,approval=prepared(episode,demo,core)
    checkpoint=episode.checkpoint();before=digest(checkpoint)
    bad=copy.deepcopy(checkpoint);bad.region_label='Changed after observation'
    with pytest.raises(SimulationRejected):episode.advance(bad,run.plan,approval,state=run.state)
    assert digest(episode.checkpoint())==before


def test_checkpoint_does_not_reveal_unobserved_resource_truth(demo,truth):
    t=truth.model_copy(deep=True);t.future_events=[event()]
    t.crews[0].available_until_min=200  # hidden mismatch; not a revealed crew event
    t.generators[0].autonomy_minutes=60  # true expiry90, public expectation150
    episode=IncidentEpisode(demo,t)
    first,_,_=prepared(episode,demo,CoreSession())
    checkpoint=episode.checkpoint()
    assert next(c for c in checkpoint.crews if c.crew_id=='C1').available_until_min==720
    assert checkpoint.active_generators[0].expires_at_min==150
    assert all(row['t']<=60 for row in first.trajectory)
    assert 'future_events' not in checkpoint.model_dump_json()


def test_lost_crews_partial_repair_restarts_without_credit(demo,truth):
    from sim_helpers import act
    s=demo.model_copy(deep=True);s.observed_state.sites['S02'].equipment_ok=False
    t=truth.model_copy(deep=True);t.sites['S02'].equipment_ok=False;t.future_events=[event()]
    episode=IncidentEpisode(s,t)
    p=make_plan([GEN_S02('C1'),act('EQ-S02','equipment_repair','S02','C2',['DEPOT','S02'],0,15,75)])
    first=episode.advance(s,p,make_approval(p))
    assert first.run_metadata['action_outcomes']['EQ-S02']['status']=='paused'
    assert first.metrics['weighted_available_so_far_min']==0
    core=CoreSession();core._next_state_version=2
    final,run,_=prepared(episode,episode.checkpoint(),core)
    repair=next(a for a in run.plan.actions if a.action_id=='EQ-S02')
    assert repair.work_start_min==60 and repair.work_end_min==120  # full60, not remaining15
    assert final.metrics['weighted_available_min']==6*30
    assert final.metrics['weighted_downtime_min']==9*720-180
    assert final.metrics['first_restoration_min']==120


def test_missing_approval_cannot_advance_any_world_state(demo,truth):
    episode=IncidentEpisode(demo,truth)
    with pytest.raises(SimulationRejected,match='approval'):
        episode.advance(demo,make_plan([GEN_S02()]),None)
    assert not episode.paused and not episode.complete


def test_simultaneous_loss_completes_work_before_interrupt(demo,truth):
    t=truth.model_copy(deep=True);t.future_events=[event(at=30)]
    episode=IncidentEpisode(demo,t);p=make_plan([GEN_S02('C2')])
    first=episode.advance(demo,p,make_approval(p))
    assert first.run_metadata['action_outcomes']['GEN-G1-S02']['status']=='completed'
    assert episode.checkpoint().active_generators[0].expires_at_min==150
    assert first.metrics['weighted_available_so_far_min']==0  # no positive interval after event scored yet
