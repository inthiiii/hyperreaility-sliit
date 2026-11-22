import pytest
from pydantic import ValidationError
from project.core.schemas import ScenarioInput,EvidenceFact
from project.core.state import build_verified_state
from project.agents.extraction import template_facts

def test_raw_input_preserves_unknown(load_case):
    s=load_case();assert s.observed_state.sites['S02'].grid_power_ok is None
    assert s.model_dump(by_alias=True)['roads'][0]['from']=='DEPOT'

@pytest.mark.parametrize('mutation',[lambda x:x['sites'].append(x['sites'][0]),lambda x:x['links'][0].update(parent='missing'),
 lambda x:x['links'][0].update(parent='S03'),lambda x:x['reports'][0].update(received_at_min=900),
 lambda x:x['action_options'][0].update(duration_minutes=0),lambda x:x['services'][0].update(weight=99),
 lambda x:x.update(evaluation_truth={'secret':True}),lambda x:x['observed_state']['links'].update(L01='false')])
def test_reject_invalid_inputs(load_case,mutation):
    raw=load_case().model_dump(by_alias=True);mutation(raw)
    with pytest.raises(ValidationError):ScenarioInput.model_validate(raw)

def test_authoritative_facts_resolve(state):
    assert state.resolved_observations.sites['S02'].grid_power_ok is False
    assert state.resolved_observations.links['L01'] is False
    assert not state.unresolved_facts

@pytest.mark.parametrize('name',['DEV-006','DEV-008'])
def test_conflict_or_missing_remains_unknown(load_case,name):
    s=load_case(name);state=build_verified_state(s,template_facts(s))
    assert state.resolved_observations.sites['S01'].equipment_ok is None
    assert state.unresolved_facts

def test_stale_unverified_cannot_overrule_authority(load_case):
    s=load_case('DEV-007');state=build_verified_state(s,template_facts(s))
    assert state.resolved_observations.sites['S01'].equipment_ok is True

def test_invented_citation_rejected(load_case):
    s=load_case();f=EvidenceFact(target_type='site',target_id='S02',attribute='grid_power_ok',value=True,evidence_ids=['FAKE'],status='verified')
    with pytest.raises(ValueError):build_verified_state(s,[f])

def test_extracted_time_must_match_evidence(load_case):
    s=load_case();facts=template_facts(s);facts[0].observed_at_min=99
    with pytest.raises(ValueError):build_verified_state(s,facts)

def test_resolution_does_not_mutate_visible_input(load_case):
    s=load_case();original=s.model_dump_json()
    build_verified_state(s,template_facts(s))
    assert s.model_dump_json()==original
