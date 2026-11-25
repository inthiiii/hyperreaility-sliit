"""Audited clarification, explicit corrections and approval invalidation."""
import json
from pathlib import Path
import shutil

import pytest
from streamlit.testing.v1 import AppTest

from project.core.schemas import Report,ScenarioInput
from project.core.state import build_verified_state,digest
from project.llm.client import HostedAdapter
from project.ui.backend import connect_static_backend
from project.ui.catalog import load_catalog
from project.ui.confirmation_service import confirm_fact,confirmation_binding
from project.ui.continuation import accept_checkpoint
from project.ui.history_data import load_history
from project.ui.local_records import read_record
from project.ui.planning_service import prepare_plan
from project.ui.review_service import ReviewBlocked,record_decision,review_context
from project.ui.session import DashboardSession,SESSION_KEY
from project.ui.simulation_service import simulate_approved

ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture
def root(tmp_path,monkeypatch):
    for split,sid in [('demo','DEMO-005'),('development','DEV-006'),('development','DEV-008'),('development','DEV-010')]:
        for folder in ['processed/agent_inputs','evaluation/ground_truth']:
            src=ROOT/'data'/folder/split/(sid+'.json');dst=tmp_path/'data'/folder/split/(sid+'.json')
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    def no_api(*args,**kwargs):raise AssertionError('Clarification must not call the hosted model')
    monkeypatch.setattr(HostedAdapter,'from_env',no_api)
    return tmp_path


def select(root,sid='DEV-006'):
    choice=next(c for c in load_catalog(root).choices if c.scenario.scenario_id==sid)
    session=DashboardSession();session.select(choice);connect_static_backend(session,choice,root)
    return session,choice


def confirm(session,choice,root,value=False,**kwargs):
    parameters={'target_type':'site','target_id':'S01','attribute':'equipment_ok','value':value,
                'operator_id':'Rehearsal operator','verification_source':'Synthetic operator inspection reference QA-1',
                'note':'Synthetic verification for the operator-workflow test','acknowledged':True}
    parameters.update(kwargs)
    return confirm_fact(session,choice,confirmation_binding(session,choice),root=root,**parameters)


def plan(session,choice,root):
    return prepare_plan(session,choice,'template','cp_sat',root)


def approve(session,choice,root):
    record_decision(session,choice,review_context(session,choice)[1],'approve','Rehearsal operator','Reviewed',root)


@pytest.mark.parametrize('sid',['DEV-006','DEV-008'])
def test_conflict_or_unknown_resolves_only_after_recorded_confirmation(root,sid):
    session,choice=select(root,sid);raw=(root/choice.key).read_bytes()
    assert plan(session,choice,root)=='escalated'
    prior=session.core.current.state.state_version
    assert confirm(session,choice,root)=='recorded'
    revised=session.confirmation_choice
    record=session.confirmation_history[-1]
    assert record.updated_state.state_version>prior
    assert record.updated_state.resolved_observations.sites['S01'].equipment_ok is False
    assert session.core.current is None and session.core.approval is None
    assert revised.scenario.reports[:-1]==choice.scenario.reports
    assert (root/choice.key).read_bytes()==raw
    assert not session.select(choice)  # passive rerender preserves the active clarification
    assert plan(session,revised,root)=='awaiting_approval'
    assert session.core.current.state.state_version>record.updated_state.state_version
    assert session.core.current.model_usage==[]
    assert session.core.approval is None
    approve(session,revised,root)
    assert simulate_approved(session,revised,review_context(session,revised)[1],'Rehearsal operator',root)=='completed'
    history=load_history(root)
    assert not history.issues and any(e.kind=='confirmation' for e in history.entries)


def test_material_fact_update_revokes_an_existing_approval(root):
    session,choice=select(root,'DEMO-005');assert plan(session,choice,root)=='awaiting_approval'
    approve(session,choice,root);old=session.core.approval
    confirm(session,choice,root,value=True)
    assert session.core.approval is None and session.core.current is None
    revised=session.confirmation_choice
    with pytest.raises(ReviewBlocked):simulate_approved(session,revised,'old binding','Rehearsal operator',root)
    assert any(r.approval == old for r in session.decision_history)  # prior audit is retained, not active
    with pytest.raises(ValueError):session.core.simulate()


def test_audit_failure_activates_no_evidence_and_revokes_prior_approval(root,monkeypatch):
    import project.ui.confirmation_service as service
    session,choice=select(root,'DEMO-005');plan(session,choice,root);approve(session,choice,root)
    def fail(*args):raise OSError('test storage failure')
    monkeypatch.setattr(service,'save_record',fail)
    with pytest.raises(OSError):confirm(session,choice,root)
    assert session.core.approval is None and session.confirmation_choice is None
    assert session.scenario_hash==choice.content_hash and not session.confirmation_history


def test_stale_form_and_changed_source_are_rejected(root):
    session,choice=select(root);binding=confirmation_binding(session,choice)
    plan(session,choice,root)
    with pytest.raises(ReviewBlocked,match='changed'):
        confirm_fact(session,choice,binding,'site','S01','equipment_ok',False,'Operator','source','reason',True,root)
    p=root/choice.key;p.write_text(p.read_text().replace('Fictional site 01','Changed site 01'))
    with pytest.raises(ReviewBlocked,match='input file changed'):confirm(session,choice,root)
    assert not session.confirmation_history


@pytest.mark.parametrize('changes',[{'operator_id':''},{'verification_source':''},{'note':''},{'acknowledged':False},
                                    {'value':'false'},{'target_id':'UNKNOWN'},{'attribute':'future_events'}])
def test_invalid_or_unacknowledged_confirmation_has_no_effect(root,changes):
    session,choice=select(root)
    with pytest.raises(ReviewBlocked):confirm(session,choice,root,**changes)
    assert not session.confirmation_history and session.confirmation_choice is None


def test_double_submission_is_idempotent_and_explicit_correction_preserves_reports(root):
    session,choice=select(root);binding=confirmation_binding(session,choice)
    args=(session,choice,binding,'site','S01','equipment_ok',False,'Operator','Field reference','Verified test',True,root)
    assert confirm_fact(*args)=='recorded'
    assert confirm_fact(*args)=='duplicate'
    first=session.confirmation_choice;old=first.scenario.reports[-1]
    confirm(session,first,root,value=True)
    second=session.confirmation_choice
    assert second.scenario.reports[-1].supersedes_report_ids==[old.report_id]
    assert second.scenario.reports[:-1]==first.scenario.reports
    assert build_verified_state(second.scenario,[]).resolved_observations.sites['S01'].equipment_ok is True
    assert len(list((root/'results/local_runs/confirmations').glob('*.json')))==2
    assert session.confirmation_history[1].updated_state.state_version>session.confirmation_history[0].updated_state.state_version


def test_confirmation_cannot_supersede_other_assets_or_original_field_reports(root):
    _,choice=select(root)
    payload=choice.scenario.model_dump(mode='json',by_alias=True)
    payload['reports'].append({'report_id':'OP-1','source_type':'operator_confirmation','observed_at_min':5,'received_at_min':5,
                               'text':'S01: equipment has failed.','supersedes_report_ids':['REP-001']})
    with pytest.raises(ValueError):ScenarioInput.model_validate(payload)
    payload['reports'][-1].pop('supersedes_report_ids')
    payload['reports'].append({'report_id':'OP-2','source_type':'operator_confirmation','observed_at_min':5,'received_at_min':5,
                               'text':'S02: equipment is operational.','supersedes_report_ids':['OP-1']})
    scenario=ScenarioInput.model_validate(payload)
    with pytest.raises(ValueError,match='same fact'):build_verified_state(scenario,[])


def test_old_report_serialization_and_hashes_do_not_gain_empty_metadata(root):
    _,choice=select(root)
    raw=json.loads((root/choice.key).read_text())
    assert [r.model_dump() for r in choice.scenario.reports]==raw['reports']


def test_later_completed_repair_supersedes_earlier_fault_confirmation(root):
    session,choice=select(root)
    confirm(session,choice,root)
    scenario=session.confirmation_choice.scenario.model_copy(deep=True)
    payload=scenario.model_dump(mode='json',by_alias=True);payload['current_time_min']=60
    payload['reports'].append({'report_id':'SIM-EQ-S01','source_type':'simulated_completion',
        'observed_at_min':60,'received_at_min':60,'text':'S01: equipment is operational.'})
    state=build_verified_state(ScenarioInput.model_validate(payload),[])
    assert state.resolved_observations.sites['S01'].equipment_ok is True


def test_confirmation_on_live_checkpoint_does_not_reset_incident_metrics(root):
    session,choice=select(root,'DEV-010');plan(session,choice,root);approve(session,choice,root)
    assert simulate_approved(session,choice,review_context(session,choice)[1],'Rehearsal operator',root)=='completed'
    with pytest.raises(ReviewBlocked,match='paused event update'):confirm(session,choice,root)
    checkpoint=accept_checkpoint(session,choice,root)
    confirm(session,checkpoint,root,value=False)
    clarified=session.continuation_choice
    assert clarified.scenario.current_time_min==60
    assert plan(session,clarified,root)=='awaiting_approval'
    approve(session,clarified,root)
    assert simulate_approved(session,clarified,review_context(session,clarified)[1],'Rehearsal operator',root)=='completed'
    assert session.simulation_result.metrics['weighted_downtime_min']==9250


def test_browser_confirm_replan_reapprove_and_history(root,monkeypatch):
    monkeypatch.setenv('RELINK_CONFIRM_ROOT',str(root))
    at=AppTest.from_string("import os\nfrom project.ui.app import render_app\nrender_app(os.environ['RELINK_CONFIRM_ROOT'])",default_timeout=30).run()
    key=next(c.key for c in load_catalog(root).choices if c.scenario.scenario_id=='DEV-006')
    at.selectbox(key='scenario_picker').set_value(key).run()
    at.radio(key='workspace_page').set_value('Planning').run()
    at.button(key='generate_plan').click().run()
    assert at.button(key='approve_plan').disabled
    at.selectbox(key='confirmation_target').set_value('site:S01:equipment_ok')
    at.selectbox(key='confirmation_value').set_value('False — failed / unavailable / closed')
    at.text_input(key='confirmation_source').set_value('Synthetic field inspection QA-1')
    at.text_area(key='confirmation_note').set_value('Test operator confirms equipment failure in the fictional incident.')
    at.checkbox(key='confirmation_ack').check()
    next(b for b in at.button if b.label=='Record confirmation and invalidate plan').click().run()
    assert not at.exception
    assert at.session_state[SESSION_KEY].core.approval is None
    at.button(key='generate_plan').click().run()
    assert not at.exception and not at.button(key='approve_plan').disabled
    at.button(key='approve_plan').click().run();at.button(key='simulate_plan').click().run()
    assert not at.exception and at.session_state[SESSION_KEY].simulation_result is not None
    at.radio(key='workspace_page').set_value('History').run()
    at.selectbox(key='history_kind').set_value('confirmation').run()
    assert not at.exception
    assert any('1 matching records' in c.value for c in at.caption)


def test_operator_assertion_never_patches_hidden_physical_truth(root):
    session,choice=select(root)
    confirm(session,choice,root,value=True)  # deliberately wrong assertion in a synthetic test
    revised=session.confirmation_choice
    assert plan(session,revised,root)=='awaiting_approval'
    assert session.core.current.state.resolved_observations.sites['S01'].equipment_ok is True
    approve(session,revised,root)
    assert simulate_approved(session,revised,review_context(session,revised)[1],'Rehearsal operator',root)=='completed'
    # Truth still has failed equipment; the claim cannot fabricate restoration.
    assert session.simulation_result.metrics['unmet_needs_count']>0
    assert session.simulation_result.metrics['weighted_downtime_min']>0


def test_two_contradictory_confirmations_without_explicit_supersession_stay_unresolved(root):
    _,choice=select(root)
    payload=choice.scenario.model_dump(mode='json',by_alias=True)
    for i,phrase in enumerate(['equipment has failed','equipment is operational']):
        payload['reports'].append({'report_id':f'OP-{i}','source_type':'operator_confirmation',
            'observed_at_min':5,'received_at_min':5,'text':f'S01: {phrase}.'})
    state=build_verified_state(ScenarioInput.model_validate(payload),[])
    assert state.resolved_observations.sites['S01'].equipment_ok is None
