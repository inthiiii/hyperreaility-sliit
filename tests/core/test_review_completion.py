"""Bounded reviewer clarification never substitutes for explicit approval."""
import json
import csv
import io
from pathlib import Path
import pytest
from project.core.coordinator import Coordinator,approve_run
from project.core.schemas import ScenarioInput
from project.agents.context import action_catalog,observations_view,plan_view
from project.core.planner import plan
from project.core.state import build_verified_state,digest
from test_models import adapter,batch,finding,review
from test_matched_workflow import hold,finding_with


def review_json(decision,**changes):
    value={'decision':decision,'findings':[],'evidence_ids':['REP-001']}
    value.update(changes);return json.dumps(value)


def test_empty_revision_gets_bounded_clarification_before_explicit_approval(load_case):
    s=load_case();a=adapter([batch(s),finding(),finding(),review_json('revise'),review()])
    result=Coordinator(a).run(s,'multi')
    assert result.status=='awaiting_approval' and len(a.client.requests)==5
    schedules=[m for m in result.messages if m['sender']=='deterministic_scheduler']
    assert len(schedules)==1
    payload=json.loads(a.client.requests[-1]['messages'][1]['content'])
    assert payload['review_feedback']['issue'] and payload['review_feedback']['arithmetic_checks']
    assert payload['review_feedback']['arithmetic_checks'][0]['computed_work_end_min']==result.plan.actions[0].work_end_min
    assert approve_run(result,'test operator').plan_id==result.plan.plan_id


def test_approval_can_acknowledge_an_existing_hold_without_changing_it(load_case):
    s=load_case();before=digest(s)
    a=adapter([batch(s),finding_with(hold()),finding(),review_json('approve',requests=[hold()])])
    result=Coordinator(a).run(s,'multi')
    assert result.status=='awaiting_approval' and result.validation.valid
    assert len(result.metadata['decision_effects'])==1 and len(a.client.requests)==4
    assert digest(s)==before and 'GEN-G1-S02' not in {a.action_id for a in result.plan.actions}


def test_approval_with_a_new_hold_must_be_reviewed_again_or_escalated(load_case):
    s=load_case()
    a=adapter([batch(s),finding(),finding(),review_json('approve',requests=[hold()]),review('escalate')])
    result=Coordinator(a).run(s,'multi')
    assert result.status=='escalated' and len(a.client.requests)==5
    assert result.metadata['decision_effects'] and result.state.state_version==2
    assert 'GEN-G1-S02' not in {a.action_id for a in result.plan.actions}
    with pytest.raises(ValueError):approve_run(result,'operator')


def test_typed_revision_is_concrete_without_a_duplicate_text_summary(load_case):
    s=load_case()
    a=adapter([batch(s),finding(),finding(),review_json('revise',requests=[hold()]),review()])
    result=Coordinator(a).run(s,'multi')
    assert result.status=='awaiting_approval' and result.state.state_version==2
    assert result.validation.valid and 'GEN-G1-S02' not in {a.action_id for a in result.plan.actions}
    assert len([m for m in result.messages if m['sender']=='deterministic_scheduler'])==2


def test_unusable_review_cannot_loop_forever_or_silently_be_approved(load_case):
    s=load_case();bad=review_json('revise',revision_kind='schedule',revision_request='Do unsupported work')
    a=adapter([batch(s),finding(),finding(),bad,bad,bad,bad])
    result=Coordinator(a).run(s,'multi')
    assert result.status=='escalated' and len(a.client.requests)==7
    assert len([m for m in result.messages if m['sender']=='deterministic_scheduler'])==1
    with pytest.raises(ValueError):approve_run(result,'operator')


def test_no_feedback_ablation_still_cannot_use_review_clarification(load_case):
    s=load_case();a=adapter([batch(s),finding(),finding(),review_json('revise')])
    result=Coordinator(a,feedback_enabled=False).run(s,'multi')
    assert result.status=='escalated' and len(a.client.requests)==4


@pytest.mark.parametrize('path',sorted((Path(__file__).resolve().parents[2]/'data/processed/agent_inputs/development').glob('*.json')))
def test_compact_operational_tables_retain_all_action_and_observation_information(path):
    s=ScenarioInput.model_validate_json(path.read_text());catalog=action_catalog(s.action_options)
    decoded=[]
    for row in csv.reader(io.StringIO(catalog['actions'])):
        row[1]=int(row[1])
        value=dict(zip(catalog['action_fields'],row));index=value.pop('spec_index')
        value.update(zip(catalog['spec_fields'],catalog['specs'][index]));decoded.append(value)
    assert decoded==[a.model_dump(mode='json') for a in s.action_options]
    obs=observations_view(s.observed_state)
    decoded_obs={'sites':{},'links':{},'roads':{}}
    for sid in s.observed_state.sites:
        decoded_obs['sites'][sid]={}
        for attr in ('equipment_ok','grid_power_ok'):
            decoded_obs['sites'][sid][attr]=None if sid in obs['site_'+attr+'_unknown'] else False if sid in obs['site_'+attr+'_false'] else obs['default']
    for typ,items in (('links',s.observed_state.links),('roads',s.observed_state.roads)):
        decoded_obs[typ]={key:None if key in obs[typ+'_unknown'] else False if key in obs[typ+'_false'] else obs['default'] for key in items}
    assert decoded_obs==s.observed_state.model_dump(mode='json')



def test_compact_plan_keeps_every_scheduled_action_field(load_case):
    s=load_case();state=build_verified_state(s,[]);p=plan(state);view=plan_view(p)
    assert [dict(zip(view['action_fields'],row)) for row in view['actions']]==[a.model_dump(mode='json') for a in p.actions]
    assert {k:v for k,v in view.items() if k not in ('actions','action_fields')}=={k:v for k,v in p.model_dump(mode='json').items() if k!='actions'}


def test_approve_with_new_hold_cannot_authorize_the_earlier_candidate(load_case):
    s=load_case();a=adapter([batch(s),finding(),finding(),review_json('approve',requests=[hold()]),review()])
    result=Coordinator(a).run(s,'multi')
    schedules=[m['finding'] for m in result.messages if m['sender']=='deterministic_scheduler']
    assert result.status=='awaiting_approval' and len(a.client.requests)==5 and len(schedules)==2
    assert schedules[0]['state_version']==1 and schedules[1]['state_version']==2
    assert 'GEN-G1-S02' not in {a.action_id for a in result.plan.actions}
    assert approve_run(result,'operator').plan_id==schedules[1]['plan_id']


def test_operational_csv_handles_quoted_ids_and_unknown_values():
    from project.agents.context import csv_table
    rows=[['A,"B',True,None],['S\n1',False,True]]
    decoded=list(csv.reader(io.StringIO(csv_table(rows))))
    assert [[row[0],json.loads(row[1]),json.loads(row[2])] for row in decoded]==rows


def test_recognized_report_objection_returns_public_source_checks_before_reextract(load_case):
    s=load_case();a=adapter([batch(s),finding(),finding(),review('revise'),review()])
    result=Coordinator(a).run(s,'multi')
    assert result.status=='awaiting_approval' and len(a.client.requests)==5
    payload=json.loads(a.client.requests[-1]['messages'][1]['content'])
    assert payload['review_feedback']['exact_report_checks']
    assert result.state.state_version==1


def test_unrecognized_report_correction_can_still_reinvoke_investigator(load_case):
    from project.core.schemas import Report
    s=load_case();s.reports.append(Report(report_id='NATURAL',source_type='confirmed_field_update',
        observed_at_min=0,received_at_min=0,text='Inspection confirms the S02 mains supply remains unavailable.'))
    revise=review_json('revise',evidence_ids=['NATURAL'],revision_request='Check the natural-language mains-supply observation.')
    a=adapter([batch(s),finding(),finding(),revise,batch(s),finding(),finding(),review()])
    result=Coordinator(a).run(s,'multi')
    assert result.status=='awaiting_approval' and result.state.state_version==2
    assert len([m for m in result.messages if m['sender']=='network_investigator'])==2


def test_missing_snapshot_values_are_rejected_before_sparse_encoding(load_case):
    s=load_case();raw=s.model_dump(mode='json')
    raw['observed_state']['sites'].pop(s.sites[0].site_id)
    with pytest.raises(ValueError):ScenarioInput.model_validate(raw)


def test_rejected_semantic_output_is_audited_but_never_approved(load_case):
    s=load_case()
    invalid=json.dumps({'clarification_required':False,'requests':[],
                        'evidence_ids':['INVENTED-REPORT'],'finding':'Unsupported claim'})
    result=Coordinator(adapter([batch(s),invalid])).run(s,'multi')
    assert result.status=='escalated'
    rejected=[m for m in result.messages if m['sender']=='rejected_agent_output']
    assert len(rejected)==1
    assert rejected[0]['finding']['validation_error']=='Agent cited nonexistent evidence'
    assert rejected[0]['finding']['output']['evidence_ids']==['INVENTED-REPORT']
    with pytest.raises(ValueError):approve_run(result,'operator')
