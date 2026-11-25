"""Real data -> planner -> operator -> paused episode -> fresh approval -> result."""
from pathlib import Path
import shutil

import pytest
from streamlit.testing.v1 import AppTest

from project.ui.backend import connect_static_backend
from project.ui.catalog import load_catalog
from project.ui.continuation import accept_checkpoint
from project.ui.history_data import load_history, linked_simulation
from project.ui.planning_service import prepare_plan
from project.ui.review_service import ReviewBlocked, record_decision, review_context, active_approval
from project.ui.session import DashboardSession, SESSION_KEY
from project.ui.simulation_service import simulate_approved

ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture
def root(tmp_path):
    for relative in ['processed/agent_inputs/development/DEV-010.json',
                     'evaluation/ground_truth/development/DEV-010.json']:
        target=tmp_path/'data'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/'data'/relative,target)
    return tmp_path


def execute(session,choice,root):
    assert prepare_plan(session,choice,'template','cp_sat',root)=='awaiting_approval'
    binding=review_context(session,choice)[1]
    record_decision(session,choice,binding,'approve','Operator','Reviewed',root)
    assert simulate_approved(session,choice,binding,'Operator',root)=='completed'
    return session.simulation_result


def test_dynamic_ui_service_preserves_source_binding_and_episode(root):
    choice=load_catalog(root).choices[0];session=DashboardSession();session.select(choice)
    assert connect_static_backend(session,choice,root)
    first=execute(session,choice,root)
    assert first.run_metadata['replan_required'] and first.metrics['weighted_downtime_min'] is None
    old_core=session.core
    followup=accept_checkpoint(session,choice,root)
    assert session.core is old_core and session.core.approval is None
    assert not active_approval(session,followup)
    assert not session.select(choice)  # Passive catalog re-read cannot reset the live episode.
    assert session.continuation_choice==followup
    with pytest.raises(ReviewBlocked):
        simulate_approved(session,followup,'old binding','Operator',root)
    final=execute(session,followup,root)
    assert not final.run_metadata['replan_required']
    assert final.metrics['weighted_available_min']==7310
    assert final.metrics['weighted_downtime_min']==9250
    history=load_history(root)
    assert not history.issues
    simulations=[e for e in history.entries if e.kind=='simulation']
    assert len(simulations)==2
    assert all(linked_simulation(e,history)[1] is None for e in simulations)
    # Changing base data invalidates any continuation before execution.
    p=root/choice.key;p.write_text(p.read_text().replace('Fictional site 01','Modified site 01'))
    with pytest.raises(ReviewBlocked):
        from project.ui.review_service import ensure_current_source
        ensure_current_source(session,followup,root)


def test_browser_two_approvals_finish_one_incident(root,monkeypatch):
    monkeypatch.setenv('RELINK_DYNAMIC_ROOT',str(root))
    at=AppTest.from_string("import os\nfrom project.ui.app import render_app\nrender_app(os.environ['RELINK_DYNAMIC_ROOT'])",default_timeout=30).run()
    at.radio(key='workspace_page').set_value('Planning').run()
    at.button(key='generate_plan').click().run();at.button(key='approve_plan').click().run()
    at.button(key='simulate_plan').click().run()
    assert not at.exception
    assert at.session_state[SESSION_KEY].simulation_result.run_metadata['replan_required']
    at.radio(key='workspace_page').set_value('Results').run()
    assert any('PARTIAL EPISODE' in w.value for w in at.warning)
    at.radio(key='workspace_page').set_value('Planning').run()
    at.button(key='accept_event_update').click().run()
    assert not at.exception and at.button(key='approve_plan').disabled
    assert not at.text_area(key='review_note').value
    at.button(key='generate_plan').click().run();at.button(key='approve_plan').click().run()
    at.button(key='simulate_plan').click().run()
    assert not at.exception
    at.radio(key='workspace_page').set_value('Results').run()
    assert not at.exception
    result=at.session_state[SESSION_KEY].simulation_result
    assert result.metrics['weighted_downtime_min']==9250
    assert result.metrics['horizon_min']==720 and result.run_metadata['measurement_scope']=='complete_incident'
    at.run()
    assert len(list((root/'results/local_runs/simulation_attempts').glob('*.json')))==2
