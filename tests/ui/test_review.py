"""Human decision audit and typed simulator boundary; no live evaluator or model."""
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from project.core.integration import IntegrationNotReady
from project.core.state import digest
from project.ui.catalog import load_catalog
from project.ui.local_records import read_record
from project.ui.planning_service import prepare_plan, begin_new_attempt
from project.ui.review_service import ReviewBlocked, active_approval, record_decision, review_context
from project.ui.session import DashboardSession, SESSION_KEY
from project.ui.simulation_service import attach_simulator, simulate_approved

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def ui_root(tmp_path):
    directory = tmp_path / 'tests/core/fixtures';directory.mkdir(parents=True)
    for source in (ROOT / 'tests/core/fixtures').glob('*.json'):
        (directory / source.name).write_bytes(source.read_bytes())
    return tmp_path


@pytest.fixture
def choice(ui_root):
    catalog = load_catalog(ui_root)
    return catalog.choices[catalog.default_index]


@pytest.fixture
def prepared(choice, ui_root):
    session = DashboardSession();session.select(choice)
    assert prepare_plan(session, choice, 'template', 'cp_sat', ui_root) == 'awaiting_approval'
    return session


def decide(session, choice, root, decision='approve', operator='Test operator', note='Inspected schedule'):
    return record_decision(session, choice, review_context(session, choice)[1], decision, operator, note, root)


def fake_result(state, plan):
    return {'scenario_id': state.scenario_id, 'plan_id': plan.plan_id, 'state_version': state.state_version,
            'trajectory': [], 'completed_actions': [], 'unmet_needs': [],
            'metrics': {'injected_test_marker': 1}, 'run_metadata': {'test_only': True}}


def test_approval_is_bound_private_and_persisted_before_activation(prepared, choice, ui_root):
    assert decide(prepared, choice, ui_root) == 'approve'
    assert active_approval(prepared, choice)
    record = prepared.last_decision
    assert record.approval.plan_hash == digest(prepared.core.current.plan)
    paths = list((ui_root / 'results/local_runs/decisions').glob('*.json'))
    assert len(paths) == 1 and paths[0].stat().st_mode & 0o777 == 0o600
    payload = read_record(paths[0]);assert payload['run_id'] == prepared.core.current.run_id
    assert payload['approval']['operator_id'] == 'Test operator' and payload['authenticated'] is False
    assert prepared.simulation_result is None


def test_duplicate_decision_does_not_write_or_append_again(prepared, choice, ui_root):
    decide(prepared, choice, ui_root)
    assert decide(prepared, choice, ui_root) == 'duplicate'
    assert len(prepared.decision_history) == 1
    assert len(list((ui_root / 'results/local_runs/decisions').glob('*.json'))) == 1


def test_rejection_revokes_approval_and_is_terminal_for_this_plan(prepared, choice, ui_root):
    decide(prepared, choice, ui_root)
    assert decide(prepared, choice, ui_root, 'reject') == 'reject'
    assert not active_approval(prepared, choice) and prepared.core.approval.decision == 'reject'
    assert decide(prepared, choice, ui_root, 'reject') == 'duplicate'
    with pytest.raises(ReviewBlocked):decide(prepared, choice, ui_root, 'approve')
    assert len(prepared.decision_history) == 2


@pytest.mark.parametrize('operator,note', [('', ''), (' ' * 2, ''), ('a' * 121, ''), ('Valid', 'a' * 2001)])
def test_identity_and_note_validation(prepared, choice, ui_root, operator, note):
    with pytest.raises(ReviewBlocked):decide(prepared, choice, ui_root, operator=operator, note=note)
    assert prepared.core.approval is None and prepared.last_decision is None


def test_stale_display_binding_and_material_changes_block_decision(prepared, choice, ui_root):
    binding = review_context(prepared, choice)[1]
    prepared.core.current.plan.explanation += ' changed after display'
    with pytest.raises(ReviewBlocked):record_decision(prepared, choice, binding, 'approve', 'Operator', '', ui_root)
    assert prepared.core.approval is None


def test_post_approval_change_expires_approval(prepared, choice, ui_root):
    decide(prepared, choice, ui_root)
    prepared.core.current.plan.explanation += ' changed'
    assert not active_approval(prepared, choice)
    with pytest.raises(ReviewBlocked):review_context(prepared, choice)


def test_escalated_and_invalid_plans_cannot_be_approved(prepared, choice, ui_root):
    prepared.core.current.status = 'escalated'
    with pytest.raises(ReviewBlocked):decide(prepared, choice, ui_root)
    prepared.core.current.status = 'awaiting_approval'
    prepared.core.current.plan.actions[0].work_start_min = 0
    with pytest.raises(ReviewBlocked):decide(prepared, choice, ui_root)
    assert prepared.core.approval is None


def test_audit_write_failure_revokes_prior_approval_without_new_credit(prepared, choice, ui_root, monkeypatch):
    import project.ui.review_service as service
    decide(prepared, choice, ui_root)
    def fail(*args):raise OSError('private file path sk-secret')
    monkeypatch.setattr(service, 'save_record', fail)
    with pytest.raises(OSError):decide(prepared, choice, ui_root, 'reject')
    assert prepared.core.approval is None and not active_approval(prepared, choice)
    assert len(prepared.decision_history) == 1


def test_new_plan_and_scenario_reset_review_but_retain_session_history(prepared, choice, ui_root):
    decide(prepared, choice, ui_root)
    begin_new_attempt(prepared)
    assert prepared.last_decision is None and prepared.core.approval is None
    assert len(prepared.decision_history) == 1
    prepare_plan(prepared, choice, 'template', 'cp_sat', ui_root)
    decide(prepared, choice, ui_root)
    attach_simulator(prepared, fake_result, 'Injected test callback')
    other = next(item for item in load_catalog(ui_root).choices if item.scenario.scenario_id == 'DEV-004')
    prepared.select(other)
    assert prepared.last_decision is None and prepared.core.simulator is None and prepared.simulator_label is None
    assert len(prepared.decision_history) == 2


def test_record_tampering_is_detected(prepared, choice, ui_root):
    decide(prepared, choice, ui_root)
    path = next((ui_root / 'results/local_runs/decisions').glob('*.json'))
    value = json.loads(path.read_text());value['payload']['note'] = 'tampered';path.write_text(json.dumps(value))
    with pytest.raises(ValueError):read_record(path)


def test_no_simulator_is_an_explicit_pending_boundary(prepared, choice, ui_root):
    decide(prepared, choice, ui_root)
    with pytest.raises(IntegrationNotReady):
        simulate_approved(prepared, choice, review_context(prepared, choice)[1], 'Test operator', ui_root)
    assert not prepared.simulation_requests and prepared.simulation_result is None


def test_simulator_requires_human_approval_matching_operator_and_binding(prepared, choice, ui_root):
    attach_simulator(prepared, fake_result, 'Injected test callback')
    binding = review_context(prepared, choice)[1]
    with pytest.raises(ReviewBlocked):simulate_approved(prepared, choice, binding, 'Test operator', ui_root)
    decide(prepared, choice, ui_root)
    with pytest.raises(ReviewBlocked):simulate_approved(prepared, choice, binding, 'Another operator', ui_root)
    with pytest.raises(ReviewBlocked):simulate_approved(prepared, choice, 'stale', 'Test operator', ui_root)
    assert not prepared.simulation_requests


def test_typed_simulation_is_persisted_once_and_receives_copies(prepared, choice, ui_root):
    calls = []
    def callback(state, plan):
        calls.append(plan.plan_id)
        output = fake_result(state, plan)
        state.resolved_observations.sites['S02'].grid_power_ok = True
        plan.explanation += ' copy modified'
        return output
    attach_simulator(prepared, callback, 'Injected callback, not restoration evaluation')
    decide(prepared, choice, ui_root);binding = review_context(prepared, choice)[1]
    plan_hash = digest(prepared.core.current.plan)
    assert simulate_approved(prepared, choice, binding, 'Test operator', ui_root) == 'completed'
    assert len(calls) == 1 and digest(prepared.core.current.plan) == plan_hash
    assert prepared.simulation_result.run_metadata['test_only']
    assert simulate_approved(prepared, choice, binding, 'Test operator', ui_root) == 'duplicate'
    assert len(calls) == 1
    path = next((ui_root / 'results/local_runs/simulation_attempts').glob('*.json'))
    assert read_record(path)['status'] == 'completed'


@pytest.mark.parametrize('bad_field,bad_value', [
    ('scenario_id', 'OTHER'), ('plan_id', 'OTHER'), ('state_version', 999),
    ('completed_actions', ['INVENTED']), ('completed_actions', ['GEN-G1-S02', 'GEN-G1-S02']),
    ('metrics', {'bad': float('nan')}),
])
def test_invalid_simulation_outputs_fail_closed_and_are_not_retried(prepared, choice, ui_root, bad_field, bad_value):
    calls = []
    def callback(state, plan):
        calls.append(1);value = fake_result(state, plan);value[bad_field] = bad_value;return value
    attach_simulator(prepared, callback, 'Injected invalid callback')
    decide(prepared, choice, ui_root);binding = review_context(prepared, choice)[1]
    assert simulate_approved(prepared, choice, binding, 'Test operator', ui_root) == 'failed'
    assert prepared.simulation_result is None and not prepared.busy
    assert simulate_approved(prepared, choice, binding, 'Test operator', ui_root) == 'duplicate'
    assert len(calls) == 1


def test_simulation_start_audit_failure_prevents_callback(prepared, choice, ui_root, monkeypatch):
    import project.ui.simulation_service as service
    calls = []
    attach_simulator(prepared, lambda state, plan: calls.append(1), 'Injected callback')
    decide(prepared, choice, ui_root)
    def fail(*args):raise OSError('private path')
    monkeypatch.setattr(service, 'save_record', fail)
    assert simulate_approved(prepared, choice, review_context(prepared, choice)[1], 'Test operator', ui_root) == 'failed'
    assert not calls and prepared.simulation_result is None and not prepared.busy


def test_simulation_exception_records_only_safe_error_type(prepared, choice, ui_root):
    def callback(*args):raise RuntimeError('Bearer private-secret sk-secret-error')
    attach_simulator(prepared, callback, 'Injected failure callback')
    decide(prepared, choice, ui_root)
    assert simulate_approved(prepared, choice, review_context(prepared, choice)[1], 'Test operator', ui_root) == 'failed'
    assert prepared.simulation_attempt['error_type'] == 'RuntimeError'
    assert 'private-secret' not in json.dumps(prepared.simulation_attempt)


def review_app(ui_root, monkeypatch):
    monkeypatch.setenv('RELINK_REVIEW_TEST_ROOT', str(ui_root))
    script = '''
import os
from project.ui.app import render_app
render_app(os.environ['RELINK_REVIEW_TEST_ROOT'])
'''
    at = AppTest.from_string(script, default_timeout=20).run()
    at.radio(key='workspace_page').set_value('Planning').run()
    at.button(key='generate_plan').click().run()
    return at


def test_ui_records_approval_rejection_and_keeps_missing_simulator_disabled(ui_root, monkeypatch):
    at = review_app(ui_root, monkeypatch)
    assert not at.exception and at.button(key='approve_plan').disabled
    at.text_input(key='operator_label').input('Test operator').run()
    at.text_area(key='review_note').input('Checked route and timing').run()
    assert not at.button(key='approve_plan').disabled
    at.button(key='approve_plan').click().run()
    assert not at.exception and at.session_state[SESSION_KEY].core.approval.decision == 'approve'
    assert at.button(key='approve_plan').disabled and at.button(key='simulate_plan').disabled
    assert any('not connected' in item.value for item in at.info)
    at.radio(key='workspace_page').set_value('Settings').run()
    at.radio(key='workspace_page').set_value('Planning').run()
    assert not at.exception and len(at.session_state[SESSION_KEY].decision_history) == 1
    at.button(key='reject_plan').click().run()
    assert not at.exception and at.session_state[SESSION_KEY].core.approval.decision == 'reject'
    assert at.button(key='approve_plan').disabled and at.button(key='reject_plan').disabled


def test_ui_callback_rejects_a_click_for_a_plan_changed_after_render(ui_root, monkeypatch):
    at = review_app(ui_root, monkeypatch)
    at.text_input(key='operator_label').input('Test operator').run()
    at.session_state[SESSION_KEY].core.current.plan.explanation += ' changed between render and click'
    at.button(key='approve_plan').click().run()
    assert not at.exception and at.session_state[SESSION_KEY].core.approval is None
    assert any('changed' in item.value.lower() for item in at.error)


def test_ui_approved_injected_simulator_executes_once(ui_root, monkeypatch):
    at = review_app(ui_root, monkeypatch)
    at.text_input(key='operator_label').input('Test operator').run()
    calls = []
    def callback(state, plan):calls.append(1);return fake_result(state, plan)
    attach_simulator(at.session_state[SESSION_KEY], callback, 'Injected test-only callback')
    at.run();at.button(key='approve_plan').click().run()
    assert not at.exception and not at.button(key='simulate_plan').disabled
    at.button(key='simulate_plan').click().run()
    assert not at.exception and len(calls) == 1 and at.button(key='simulate_plan').disabled
    at.run();assert len(calls) == 1
    at.radio(key='workspace_page').set_value('Results').run()
    assert not at.exception and any('recorded' in item.value for item in at.success)


def test_disk_update_after_display_blocks_decision_and_simulation(prepared, choice, ui_root):
    decide(prepared, choice, ui_root)
    calls = []
    attach_simulator(prepared, lambda state, plan: calls.append(1), 'Injected callback')
    binding = review_context(prepared, choice)[1]
    path = ui_root / choice.key
    value = json.loads(path.read_text());value['region_label'] += ' updated on disk';path.write_text(json.dumps(value))
    with pytest.raises(ReviewBlocked):simulate_approved(prepared, choice, binding, 'Test operator', ui_root)
    assert not calls and prepared.core.approval is None
    with pytest.raises(ReviewBlocked):record_decision(prepared, choice, binding, 'approve', 'Test operator', '', ui_root)


def test_input_change_during_callback_prevents_accepting_result(prepared, choice, ui_root):
    def callback(state, plan):
        path = ui_root / choice.key
        value = json.loads(path.read_text());value['region_label'] += ' changed during callback';path.write_text(json.dumps(value))
        return fake_result(state, plan)
    attach_simulator(prepared, callback, 'Injected callback')
    decide(prepared, choice, ui_root)
    assert simulate_approved(prepared, choice, review_context(prepared, choice)[1], 'Test operator', ui_root) == 'failed'
    assert prepared.core.approval is None and prepared.simulation_result is None
