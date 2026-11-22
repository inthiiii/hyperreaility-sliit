import pytest
from project.core.planner import plan,greedy_plan
from project.core.validator import validate
from project.core.schemas import ScheduledAction
from project.core.state import build_verified_state
from project.agents.extraction import template_facts
from project.core.coordinator import approve,check_approval,Coordinator

@pytest.fixture
def scheduled(state):return plan(state,solver_seconds=3)

def test_cp_sat_restores_useful_branch(scheduled,state):
    assert validate(scheduled,state).valid
    assert len(scheduled.actions)==1
    a=scheduled.actions[0]
    assert a.kind=='generator_deploy' and a.target_id=='S02'
    assert a.work_start_min==15 and a.work_end_min==30
    assert scheduled.planner_config['solver_status'] in ['OPTIMAL','FEASIBLE']

def test_greedy_is_valid(state):assert validate(greedy_plan(state),state).valid

@pytest.mark.parametrize('mutate,expected',[
 (lambda p:p.actions[0].travel_route.__setitem__(0,'S01'),'ROUTE_ENDPOINT'),
 (lambda p:setattr(p.actions[0],'work_start_min',0),'TRAVEL_TIME'),
 (lambda p:setattr(p.actions[0],'crew_id','missing'),'REFERENCE'),
 (lambda p:p.actions.append(p.actions[0].model_copy()),'DUPLICATE'),
 (lambda p:setattr(p,'state_version',99),'STALE_STATE'),
 (lambda p:p.evidence_ids.append('invented'),'EVIDENCE'),
])
def test_independent_validator_catches_mutations(scheduled,state,mutate,expected):
    mutate(scheduled);result=validate(scheduled,state)
    assert not result.valid
    assert expected in {v.code for v in result.violations}

def test_generator_cannot_be_reused(scheduled,state):
    a=scheduled.actions[0]
    other=ScheduledAction(action_id='GEN-G1-S01',kind='generator_deploy',target_id='S01',crew_id='C2' if a.crew_id=='C1' else 'C1',
        generator_id='G1',departure_min=0,travel_route=['DEPOT','S01'],work_start_min=25,work_end_min=40)
    scheduled.actions.append(other)
    assert 'GENERATOR_REUSE' in {v.code for v in validate(scheduled,state).violations}

def test_unknown_road_is_not_routable(load_case):
    s=load_case();s.observed_state.roads['R02']=None
    state=build_verified_state(s,template_facts(s));result=plan(state,solver_seconds=1)
    assert not any(a.target_id=='S02' for a in result.actions)

def test_missing_skill_excludes_task(load_case):
    s=load_case('DEV-004');state=build_verified_state(s,template_facts(s));result=plan(state,solver_seconds=2)
    assert not any(a.kind=='link_repair' for a in result.actions)

def test_approval_bound_to_content(scheduled,state):
    a=approve(scheduled.plan_id,state.state_version,'approve',plan=scheduled,state=state,operator_id='operator')
    check_approval(a,scheduled,state)
    scheduled.explanation='Changed after approval'
    with pytest.raises(ValueError):check_approval(a,scheduled,state)

def test_new_observation_revokes_approval(scheduled,state):
    a=approve(scheduled.plan_id,state.state_version,'approve',plan=scheduled,state=state,operator_id='operator')
    state.resolved_observations.roads['R02']=False
    with pytest.raises(ValueError):check_approval(a,scheduled,state)

def test_conflict_escalates_without_planning(load_case):
    r=Coordinator().run(load_case('DEV-006'))
    assert r.status=='escalated' and r.plan is None

def test_template_mode_is_explicit(load_case):
    r=Coordinator().run(load_case())
    assert r.status=='awaiting_approval' and not r.model_usage
    assert r.messages[0]['finding']['not_llm']

def test_independent_prediction_matches_reference(scheduled):
    assert scheduled.planner_config['predicted_weighted_available_minutes_remaining']==720
    assert scheduled.planner_config['predicted_weighted_downtime_remaining']==5760

def test_full_power_loss_without_generator_does_not_claim_recovery(state):
    state.scenario.generators[0].available=False
    p=plan(state,solver_seconds=1)
    assert not any(a.kind=='generator_deploy' for a in p.actions)
    assert p.planner_config['predicted_weighted_available_minutes_remaining']==0
    assert any('Grid outage' in reason for reason in p.unmet_needs)

def test_wrong_crew_skill_is_rejected(state):
    p=greedy_plan(state)
    link=next(a for a in p.actions if a.kind=='link_repair')
    link.crew_id='C1'
    assert 'SKILL' in {v.code for v in validate(p,state).violations}

def test_real_overlap_is_rejected(state):
    p=greedy_plan(state)
    # Force a legitimate second action onto the generator crew during its first task.
    generator=next(a for a in p.actions if a.kind=='generator_deploy')
    link=next(a for a in p.actions if a.kind=='link_repair')
    link.crew_id=generator.crew_id;link.departure_min=0
    assert 'CREW_OVERLAP' in {v.code for v in validate(p,state).violations}

def test_closed_route_rejected(scheduled,state):
    state.resolved_observations.roads['R02']=False
    assert 'ROUTE_CLOSED' in {v.code for v in validate(scheduled,state).violations}

def test_generator_transport_cannot_teleport(scheduled,state):
    state.scenario.generators[0].location='S01'
    assert 'GENERATOR_TRANSPORT' in {v.code for v in validate(scheduled,state).violations}
