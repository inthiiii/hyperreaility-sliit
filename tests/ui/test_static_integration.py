"""Offline composition tests with Zahra's optional, real static backend."""
from pathlib import Path
import shutil

import pytest
from streamlit.testing.v1 import AppTest

from project.ui import backend
from project.ui.catalog import load_catalog
from project.ui.history_data import load_history
from project.ui.outcome_data import current_outcome, metric_rows, service_interval_rows
from project.ui.planning_service import prepare_plan
from project.ui.review_service import ReviewBlocked, record_decision, review_context
from project.ui.session import DashboardSession, SESSION_KEY
from project.ui.simulation_service import simulate_approved

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def case(tmp_path):
    pytest.importorskip('project.simulation.engine')
    for relative in ['processed/agent_inputs/demo/DEMO-005.json',
                     'evaluation/ground_truth/demo/DEMO-005.json']:
        target = tmp_path / 'data' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'data' / relative, target)
    catalog = load_catalog(tmp_path)
    choice = catalog.choices[catalog.default_index]
    session = DashboardSession(); session.select(choice)
    return session, choice, tmp_path


def prepare(case):
    session, choice, root = case
    assert backend.connect_static_backend(session, choice, root)
    assert prepare_plan(session, choice, 'template', 'cp_sat', root) == 'awaiting_approval'
    return session, choice, root, review_context(session, choice)[1]


def approve(case):
    session, choice, root, binding = prepare(case)
    record_decision(session, choice, binding, 'approve', 'Operator', '', root)
    return session, choice, root, binding


def test_missing_backend_keeps_data_only_app_usable(monkeypatch):
    catalog = load_catalog(ROOT); choice = catalog.choices[catalog.default_index]
    session = DashboardSession(); session.select(choice)
    def missing(name): raise ModuleNotFoundError(name)
    monkeypatch.setattr(backend, 'import_module', missing)
    assert not backend.connect_static_backend(session, choice, ROOT)
    assert session.core.simulator is None


def test_attachment_never_reads_truth_and_preserves_existing_callback(case, monkeypatch):
    from project.data.evaluator import EvaluatorLoader
    def forbidden(*args): raise AssertionError('Passive rendering cannot read evaluator truth')
    monkeypatch.setattr(EvaluatorLoader, 'load', forbidden)
    session, choice, root = case
    assert backend.connect_static_backend(session, choice, root)
    original = session.core.simulator
    assert backend.connect_static_backend(session, choice, root)
    assert session.core.simulator is original


def test_static_demo_approved_measured_recorded_and_not_repeated(case):
    session, choice, root, binding = approve(case)
    assert simulate_approved(session, choice, binding, 'Operator', root) == 'completed'
    result, issue = current_outcome(session)
    assert not issue and result.metrics['weighted_downtime_min'] == 5760
    assert result.metrics['weighted_available_min'] == 720
    assert result.metrics['first_restoration_min'] == 30
    assert result.run_metadata['planner_prediction_used'] is False
    assert result.run_metadata['integration_scope'] == 'static_episode'
    assert all(row['Unit'] != 'Not specified' for row in metric_rows(result))
    assert [(r['Service'], r['Start (min)'], r['End (min)']) for r in service_interval_rows(result)] == [
        ('V02', 30, 150), ('V04', 30, 150)]
    assert simulate_approved(session, choice, binding, 'Operator', root) == 'duplicate'
    history = load_history(root)
    assert not history.issues and any(e.kind == 'simulation' and e.status == 'completed' for e in history.entries)
    assert session.core.current.model_usage == []


def test_real_callback_cannot_bypass_operator_approval(case):
    session, choice, root, binding = prepare(case)
    with pytest.raises(ReviewBlocked):
        simulate_approved(session, choice, binding, 'Operator', root)
    assert session.simulation_result is None


def test_new_selection_gets_fresh_core_and_callback(case):
    from dataclasses import replace
    session, choice, root, binding = approve(case)
    old_core = session.core
    session.select(replace(choice, key=choice.key + '-changed'))
    assert session.core is not old_core and session.core.approval is None
    assert backend.connect_static_backend(session, choice, root)
    assert session.core.simulator is not None
    assert session.simulation_result is None


def test_dynamic_case_publishes_no_partial_measurements(case, monkeypatch):
    from project.data.evaluator import EvaluatorLoader
    session, choice, root, binding = approve(case)
    truth = EvaluatorLoader(root / 'data/evaluation/ground_truth').load('DEMO-005')
    truth.future_events.append(object())
    monkeypatch.setattr(EvaluatorLoader, 'load', lambda *args: truth)
    assert simulate_approved(session, choice, binding, 'Operator', root) == 'unsupported'
    assert session.simulation_result is None and session.simulation_attempt['status'] == 'unsupported'
    assert not session.core.executed
    history = load_history(root)
    assert not history.issues and any(e.status == 'unsupported' for e in history.entries)
    assert simulate_approved(session, choice, binding, 'Operator', root) == 'duplicate'


def test_horizon_expiry_bug_is_blocked_until_backend_fixed(case, monkeypatch):
    from project.data.evaluator import EvaluatorLoader
    session, choice, root, binding = approve(case)
    truth = EvaluatorLoader(root / 'data/evaluation/ground_truth').load('DEMO-005')
    truth.generators[0].autonomy_minutes = 690  # deployment ends 30; expiry at horizon 720
    monkeypatch.setattr(EvaluatorLoader, 'load', lambda *args: truth)
    assert simulate_approved(session, choice, binding, 'Operator', root) == 'unsupported'
    assert session.simulation_result is None


def test_streamlit_click_flow_uses_real_simulator(case, monkeypatch):
    session, choice, root = case
    monkeypatch.setenv('RELINK_STATIC_TEST_ROOT', str(root))
    script = "import os\nfrom project.ui.app import render_app\nrender_app(os.environ['RELINK_STATIC_TEST_ROOT'])"
    at = AppTest.from_string(script, default_timeout=30).run()
    at.text_input(key='operator_label').set_value('Operator')
    at.radio(key='workspace_page').set_value('Planning').run()
    assert not at.exception
    # The template mode is the default and makes no model calls.
    at.button(key='generate_plan').click().run()
    assert not at.exception
    at.button(key='approve_plan').click().run()
    assert not at.exception and not at.button(key='simulate_plan').disabled
    at.button(key='simulate_plan').click().run()
    assert not at.exception
    assert at.session_state[SESSION_KEY].simulation_result.metrics['weighted_downtime_min'] == 5760
    at.radio(key='workspace_page').set_value('Results').run()
    assert not at.exception
    assert any(e.value == 'Measured service availability' for e in at.subheader)
    at.run()
    assert len(list((root / 'results/local_runs/simulation_attempts').glob('*.json'))) == 1
