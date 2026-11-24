"""Operator-visible failure walkthroughs using real development inputs, offline."""
from pathlib import Path
import shutil

import pytest
from streamlit.testing.v1 import AppTest

from project.core.integration import IntegrationNotReady
from project.llm.client import HostedAdapter
from project.ui.catalog import load_catalog
from project.ui.planning_service import prepare_plan, begin_new_attempt
from project.ui.review_service import record_decision, review_context, ReviewBlocked
from project.ui.session import DashboardSession, SESSION_KEY
from project.ui.simulation_service import attach_simulator, simulate_approved
from project.ui.workflow import workflow_status

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def demo_root(tmp_path, monkeypatch):
    for relative in ['demo/DEMO-005.json', 'development/DEV-006.json', 'development/DEV-008.json']:
        target = tmp_path / 'data/processed/agent_inputs' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'data/processed/agent_inputs' / relative, target)
    def forbidden(*args, **kwargs):
        raise AssertionError('Offline walkthrough must never initialize a hosted adapter')
    monkeypatch.setattr(HostedAdapter, 'from_env', forbidden)
    # Reproduce today's data-only application even in a backend-enabled test checkout.
    def absent_backend(name):
        raise ModuleNotFoundError(name)
    monkeypatch.setattr('project.ui.backend.import_module', absent_backend)
    return tmp_path


def selected(root, scenario_id='DEMO-005'):
    choice = next(c for c in load_catalog(root).choices if c.scenario.scenario_id == scenario_id)
    session = DashboardSession(); session.select(choice)
    return session, choice


def plan(root, scenario_id='DEMO-005'):
    session, choice = selected(root, scenario_id)
    prepare_plan(session, choice, 'template', 'cp_sat', root)
    return session, choice


def decide(session, choice, root, decision):
    return record_decision(session, choice, review_context(session, choice)[1], decision, 'Operator', 'Reviewed', root)


@pytest.mark.parametrize('scenario_id', ['DEV-006', 'DEV-008'])
def test_real_conflict_and_missing_evidence_escalate(demo_root, scenario_id):
    session, choice = plan(demo_root, scenario_id)
    assert session.core.current.status == 'escalated'
    assert session.core.current.reasons
    assert workflow_status(session, choice).code == 'escalated'
    with pytest.raises(ReviewBlocked): decide(session, choice, demo_root, 'approve')
    assert session.core.approval is None and session.simulation_result is None


def test_rejection_is_terminal_until_explicit_new_attempt(demo_root):
    session, choice = plan(demo_root)
    assert workflow_status(session, choice).code == 'review'
    old_run = session.core.current.run_id
    decide(session, choice, demo_root, 'reject')
    assert workflow_status(session, choice).code == 'rejected'
    with pytest.raises(ReviewBlocked): decide(session, choice, demo_root, 'approve')
    begin_new_attempt(session)
    assert workflow_status(session, choice).code == 'ready'
    prepare_plan(session, choice, 'template', 'cp_sat', demo_root)
    assert session.core.current.run_id != old_run and session.core.approval is None


def test_backend_pending_is_not_presented_as_simulated(demo_root):
    session, choice = plan(demo_root)
    decide(session, choice, demo_root, 'approve')
    assert workflow_status(session, choice).code == 'backend_pending'
    assert session.simulation_result is None
    session.core.current.plan.explanation += ' changed'
    assert workflow_status(session, choice).code == 'approval_expired'


def test_unsupported_attempt_has_guidance_and_no_result_or_retry(demo_root):
    session, choice = plan(demo_root)
    calls = []
    def unsupported(state, plan):
        calls.append(plan.plan_id)
        raise IntegrationNotReady('Injected unsupported test callback')
    attach_simulator(session, unsupported, 'Injected unsupported-path test')
    decide(session, choice, demo_root, 'approve')
    assert workflow_status(session, choice).code == 'approved'
    binding = review_context(session, choice)[1]
    assert simulate_approved(session, choice, binding, 'Operator', demo_root) == 'unsupported'
    assert workflow_status(session, choice).code == 'unsupported'
    assert simulate_approved(session, choice, binding, 'Operator', demo_root) == 'duplicate'
    assert len(calls) == 1 and session.simulation_result is None


def app(root, monkeypatch):
    monkeypatch.setenv('RELINK_DEMO_FLOW_ROOT', str(root))
    return AppTest.from_string("import os\nfrom project.ui.app import render_app\nrender_app(os.environ['RELINK_DEMO_FLOW_ROOT'])", default_timeout=30).run()


def test_ui_reject_retry_approve_and_scenario_change(demo_root, monkeypatch):
    at = app(demo_root, monkeypatch)
    at.text_input(key='operator_label').set_value('Operator')
    at.radio(key='workspace_page').set_value('Planning').run()
    at.button(key='generate_plan').click().run()
    at.button(key='reject_plan').click().run()
    assert not at.exception
    assert at.button(key='approve_plan').disabled and at.button(key='simulate_plan').disabled
    assert any(e.value == 'Plan rejected' for e in at.subheader)
    at.button(key='new_planning_attempt').click().run()
    at.button(key='generate_plan').click().run()
    at.button(key='approve_plan').click().run()
    assert not at.exception and at.button(key='simulate_plan').disabled
    assert any(e.value == 'Approved · awaiting simulator' for e in at.subheader)
    at.radio(key='workspace_page').set_value('Results').run()
    assert not at.exception and any(e.value == 'Approved · awaiting simulator' for e in at.subheader)
    key = next(c.key for c in load_catalog(demo_root).choices if c.scenario.scenario_id == 'DEV-006')
    at.selectbox(key='scenario_picker').set_value(key).run()
    session = at.session_state[SESSION_KEY]
    assert session.core.current is None and session.core.approval is None and session.simulation_result is None
    assert any(e.value == 'Ready to plan' for e in at.subheader)
    at.radio(key='workspace_page').set_value('Planning').run()
    at.button(key='generate_plan').click().run()
    assert not at.exception
    assert any(e.value == 'Clarification required' for e in at.subheader)
    assert at.button(key='approve_plan').disabled and at.button(key='simulate_plan').disabled
    run_id = session.core.current.run_id
    at.run()
    assert session.core.current.run_id == run_id and session.core.current.model_usage == []


def test_ui_unsupported_result_is_explained_on_planning_and_results(demo_root, monkeypatch):
    at = app(demo_root, monkeypatch)
    at.text_input(key='operator_label').set_value('Operator')
    at.radio(key='workspace_page').set_value('Planning').run()
    at.button(key='generate_plan').click().run()
    session = at.session_state[SESSION_KEY]
    def unsupported(state, plan):
        raise IntegrationNotReady('Injected unsupported test callback')
    attach_simulator(session, unsupported, 'Injected unsupported-path test')
    at.button(key='approve_plan').click().run()
    assert not at.button(key='simulate_plan').disabled
    at.button(key='simulate_plan').click().run()
    assert not at.exception and at.button(key='simulate_plan').disabled
    assert any(e.value == 'Episode support pending' for e in at.subheader)
    at.radio(key='workspace_page').set_value('Results').run()
    assert not at.exception and any(e.value == 'Episode support pending' for e in at.subheader)
    assert session.simulation_result is None
    at.run()
    assert len(list((demo_root / 'results/local_runs/simulation_attempts').glob('*.json'))) == 1
