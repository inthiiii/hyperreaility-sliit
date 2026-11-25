"""Explicit action, deduplication, failure accounting and core integration checks."""
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from project.core.coordinator import Coordinator as _LegacyCoordinator


@pytest.fixture(autouse=True)
def _legacy_hosted_workflow(monkeypatch):
    """These tests script v13 replies; they check UI plumbing, not the agent protocol."""
    monkeypatch.setattr('project.ui.planning_service.HOSTED_WORKFLOW', _LegacyCoordinator)

from streamlit.testing.v1 import AppTest

from project.agents.extraction import template_facts
from project.core.coordinator import Coordinator
from project.core.integration import CoreSession
from project.core.state import digest
from project.core.tracing import read_run
from project.llm.client import HostedAdapter
from project.ui.catalog import load_catalog
from project.ui.planning_service import (
    begin_new_attempt, fact_rows, prepare_plan, request_key, schedule_rows, timeline_rows,
)
from project.ui.session import DashboardSession, SESSION_KEY

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def ui_root(tmp_path):
    directory = tmp_path / 'tests/core/fixtures';directory.mkdir(parents=True)
    for path in (ROOT / 'tests/core/fixtures').glob('*.json'):
        (directory / path.name).write_bytes(path.read_bytes())
    return tmp_path


@pytest.fixture
def choice(ui_root):
    catalog = load_catalog(ui_root)
    return catalog.choices[catalog.default_index]


@pytest.fixture
def session(choice):
    session = DashboardSession();session.select(choice)
    return session


class FakeClient:
    def __init__(self, replies):
        self.replies = iter(replies);self.requests = [];self.closed = False
        self.chat = NS(completions=NS(create=self.create))
    def create(self, **kwargs):
        self.requests.append(kwargs)
        value = next(self.replies)
        if isinstance(value, Exception):
            raise value
        return NS(id='injected-request', model='injected-model', usage=NS(prompt_tokens=100, completion_tokens=50),
                  choices=[NS(finish_reason='stop', message=NS(content=value))])
    def close(self):
        self.closed = True


def hosted(choice, multi=False, error=None):
    facts = json.dumps({'facts': [fact.model_dump() for fact in template_facts(choice.scenario)]})
    finding = json.dumps({'finding': 'Resource/priority constraints inspected', 'evidence_ids': ['REP-001'],
                          'clarification_required': False})
    review = json.dumps({'decision': 'approve', 'findings': [], 'evidence_ids': ['REP-001'], 'revision_request': ''})
    replies = [error] if error else [facts, finding, finding, review]
    client = FakeClient(replies)
    adapter = HostedAdapter('openai', 'injected-model', 'fake-key', client=client)
    return adapter, client


def configure(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'openai');monkeypatch.setenv('LLM_MODEL', 'injected-model')
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-never-send-or-display')


def test_template_run_is_real_persisted_and_duplicate_is_noop(session, choice, ui_root, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Offline mode must not construct an adapter')
    monkeypatch.setattr(HostedAdapter, 'from_env', forbidden)
    before = digest(choice.scenario)
    assert prepare_plan(session, choice, 'template', 'cp_sat', ui_root) == 'awaiting_approval'
    result = session.core.current
    assert len(result.plan.actions) == 1 and result.plan.actions[0].target_id == 'S02'
    assert result.validation.valid and result.model_usage == [] and session.core.approval is None
    assert prepare_plan(session, choice, 'template', 'cp_sat', ui_root) == 'duplicate'
    assert session.core.current.run_id == result.run_id and digest(choice.scenario) == before
    assert read_run(ui_root / 'results/local_runs' / (result.run_id + '.json'))['run_id'] == result.run_id
    attempts = list((ui_root / 'results/local_runs/ui_attempts').glob('*.json'))
    assert len(attempts) == 1 and json.loads(attempts[0].read_text())['status'] == 'awaiting_approval'


def test_explicit_new_attempt_revokes_state_and_increases_version(session, choice, ui_root):
    prepare_plan(session, choice, 'template', 'greedy', ui_root)
    old = session.core.current;session.core.approval = object();session.simulation_result = object()
    begin_new_attempt(session)
    assert session.core.current is None and session.core.approval is None and session.simulation_result is None
    prepare_plan(session, choice, 'template', 'greedy', ui_root)
    assert session.core.current.run_id != old.run_id and session.core.current.state.state_version == 2


@pytest.mark.parametrize('mode,calls', [('single', 4), ('multi', 4)])
def test_hosted_modes_use_real_coordinator_and_close_adapter(mode, calls, session, choice, ui_root, monkeypatch):
    configure(monkeypatch);adapter, client = hosted(choice, multi=mode == 'multi')
    assert prepare_plan(session, choice, mode, 'cp_sat', ui_root, adapter_factory=lambda: adapter) == 'awaiting_approval'
    assert client.closed and len(client.requests) == calls
    result = session.core.current
    assert result.metadata['transport'] == 'injected_test_client'
    assert len(session.planning_attempt['model_usage']) == calls
    assert prepare_plan(session, choice, mode, 'cp_sat', ui_root, adapter_factory=lambda: adapter) == 'duplicate'
    assert len(client.requests) == calls


def test_missing_configuration_revokes_previous_plan_without_client(session, choice, ui_root, monkeypatch):
    prepare_plan(session, choice, 'template', 'cp_sat', ui_root)
    session.core.approval = object()
    monkeypatch.delenv('LLM_MODEL', raising=False)
    def forbidden():
        raise AssertionError('No client before valid preflight')
    assert prepare_plan(session, choice, 'single', 'cp_sat', ui_root, adapter_factory=forbidden) == 'blocked'
    assert session.core.current is None and session.core.approval is None
    assert session.planning_attempt['status'] == 'blocked' and not session.busy


def test_client_setup_failure_is_redacted_persisted_and_not_retried(session, choice, ui_root, monkeypatch):
    configure(monkeypatch);calls = []
    def fail():
        calls.append(1);raise RuntimeError('Authorization: Bearer sensitive-value sk-secret-exception')
    assert prepare_plan(session, choice, 'single', 'cp_sat', ui_root, adapter_factory=fail) == 'failed'
    assert prepare_plan(session, choice, 'single', 'cp_sat', ui_root, adapter_factory=fail) == 'duplicate'
    assert len(calls) == 1 and session.core.current is None and not session.busy
    files = list((ui_root / 'results/local_runs/ui_attempts').glob('*.json'))
    contents = files[0].read_text()
    assert 'client_setup_failed' in contents and 'sensitive-value' not in contents and 'sk-secret' not in contents


def test_provider_failure_usage_is_retained_and_old_approval_cleared(session, choice, ui_root, monkeypatch):
    configure(monkeypatch)
    prepare_plan(session, choice, 'template', 'cp_sat', ui_root)
    session.core.approval = object()
    adapter, client = hosted(choice, error=RuntimeError('sk-private-error'))
    assert prepare_plan(session, choice, 'single', 'cp_sat', ui_root, adapter_factory=lambda: adapter) == 'escalated'
    assert session.core.current.status == 'escalated' and session.core.approval is None
    assert client.closed and len(session.planning_attempt['model_usage']) == 1
    assert 'sk-private-error' not in json.dumps(session.planning_attempt)


def test_busy_request_is_noop_and_cannot_reset(session, choice, ui_root):
    session.busy = True
    assert prepare_plan(session, choice, 'template', 'cp_sat', ui_root) == 'busy'
    assert not session.planning_requests
    with pytest.raises(ValueError):begin_new_attempt(session)


def test_stale_inputs_and_unknown_modes_are_rejected(session, choice, ui_root):
    with pytest.raises(ValueError):prepare_plan(session, choice, 'unknown', 'cp_sat', ui_root)
    session.scenario_hash = 'wrong'
    with pytest.raises(ValueError):prepare_plan(session, choice, 'template', 'cp_sat', ui_root)
    session.scenario_hash = choice.content_hash
    choice.scenario.region_label += ' changed'
    with pytest.raises(ValueError):prepare_plan(session, choice, 'template', 'cp_sat', ui_root)


def test_scheduler_or_mode_change_produces_distinct_request(session, choice, monkeypatch):
    configure(monkeypatch)
    keys = {request_key(session, choice, mode, planner) for mode in ('template', 'single', 'multi')
            for planner in ('cp_sat', 'greedy')}
    assert len(keys) == 6


def test_projections_use_actual_schedule_and_facts(session, choice, ui_root):
    prepare_plan(session, choice, 'template', 'cp_sat', ui_root)
    result = session.core.current
    rows = schedule_rows(result);timeline = timeline_rows(result)
    assert rows[0]['Depart (min)'] == 0 and rows[0]['Work start (min)'] == 15 and rows[0]['Work end (min)'] == 30
    assert [(row['Stage'], row['Start'], row['End']) for row in timeline] == [('Travel', 0, 15), ('Work', 15, 30)]
    assert any(row['Attribute'] == 'grid_power_ok' and row['Value'] == 'False' for row in fact_rows(result))


def test_metadata_write_failure_does_not_repeat_inference(session, choice, ui_root, monkeypatch):
    import project.ui.planning_service as service
    def fail(*args):raise OSError('sensitive path')
    monkeypatch.setattr(service, '_save_attempt', fail)
    assert prepare_plan(session, choice, 'template', 'cp_sat', ui_root) == 'awaiting_approval'
    assert session.planning_attempt['warnings'] and not session.busy
    assert prepare_plan(session, choice, 'template', 'cp_sat', ui_root) == 'duplicate'


def test_core_versions_advance_after_failure_and_ui_clear(choice):
    session = CoreSession()
    class Failure:
        def run(self, *args, **kwargs):raise RuntimeError('failed request')
    with pytest.raises(RuntimeError):session.prepare(Failure(), choice.scenario)
    result = session.prepare(Coordinator(), choice.scenario)
    assert result.state.state_version == 2
    session.current = None
    assert session.prepare(Coordinator(), choice.scenario).state.state_version == 3


def planning_app(ui_root, monkeypatch):
    monkeypatch.setenv('RELINK_PLANNING_TEST_ROOT', str(ui_root))
    script = '''
import os
from project.ui.app import render_app
render_app(os.environ['RELINK_PLANNING_TEST_ROOT'])
'''
    at = AppTest.from_string(script, default_timeout=20).run()
    return at.radio(key='workspace_page').set_value('Planning').run()


def test_ui_real_template_run_survives_reruns_navigation_and_requires_explicit_retry(ui_root, monkeypatch):
    def forbidden(*args, **kwargs):raise AssertionError('Offline browsing/generation must not call hosted models')
    monkeypatch.setattr(HostedAdapter, 'from_env', forbidden)
    at = planning_app(ui_root, monkeypatch)
    assert not at.exception and at.session_state[SESSION_KEY].core.current is None
    at.button(key='generate_plan').click().run()
    assert not at.exception
    result = at.session_state[SESSION_KEY].core.current
    assert result.status == 'awaiting_approval' and len(result.plan.actions) == 1
    assert at.button(key='generate_plan').disabled
    assert any('independent' in element.value.lower() for element in at.info)
    for page in ('Incident', 'Overview', 'Settings', 'Planning'):
        at.radio(key='workspace_page').set_value(page).run()
        assert not at.exception and at.session_state[SESSION_KEY].core.current.run_id == result.run_id
    at.button(key='new_planning_attempt').click().run()
    assert not at.exception and at.session_state[SESSION_KEY].core.current is None
    assert not at.button(key='generate_plan').disabled
    at.button(key='generate_plan').click().run()
    assert not at.exception and at.session_state[SESSION_KEY].core.current.state.state_version == 2


def test_ui_missing_model_blocks_hosted_generation_but_selection_makes_no_calls(ui_root, monkeypatch):
    monkeypatch.delenv('LLM_MODEL', raising=False)
    def forbidden(*args, **kwargs):raise AssertionError('Selecting hosted mode must not initialize a client')
    monkeypatch.setattr(HostedAdapter, 'from_env', forbidden)
    at = planning_app(ui_root, monkeypatch)
    at.selectbox(key='planning_mode').select('single').run()
    assert not at.exception and at.button(key='generate_plan').disabled
    assert at.session_state[SESSION_KEY].core.current is None


def test_ui_scenario_change_clears_generated_result_and_request_ledger(ui_root, monkeypatch):
    at = planning_app(ui_root, monkeypatch)
    at.button(key='generate_plan').click().run()
    assert at.session_state[SESSION_KEY].core.current is not None
    at.selectbox(key='scenario_picker').select('tests/core/fixtures/DEV-004.json').run()
    assert not at.exception and at.session_state[SESSION_KEY].core.current is None
    assert not at.session_state[SESSION_KEY].planning_requests
    assert not at.button(key='generate_plan').disabled


def test_ui_hosted_click_and_rerun_use_injected_client_only(ui_root, choice, monkeypatch):
    configure(monkeypatch);adapter, client = hosted(choice)
    monkeypatch.setattr(HostedAdapter, 'from_env', lambda: adapter)
    at = planning_app(ui_root, monkeypatch)
    at.selectbox(key='planning_mode').select('single').run()
    assert not client.requests
    at.button(key='generate_plan').click().run()
    assert not at.exception and client.closed and len(client.requests) == 4
    at.run()
    assert not at.exception and len(client.requests) == 4 and at.button(key='generate_plan').disabled
    assert 'sk-never-send-or-display' not in str(at)
    run_id = at.session_state[SESSION_KEY].core.current.run_id
    at.radio(key='workspace_page').set_value('Settings').run()
    at.radio(key='workspace_page').set_value('Planning').run()
    assert not at.exception and at.selectbox(key='planning_mode').value == 'single'
    assert len(client.requests) == 4 and at.session_state[SESSION_KEY].core.current.run_id == run_id


def test_core_versions_follow_reviewer_revision_versions(choice):
    session = CoreSession()
    class Revised:
        def run(self, scenario, mode, state_version):
            result = Coordinator().run(scenario, mode, state_version=state_version)
            # Mimic a review loop that has advanced the visible state several times.
            result.state.state_version = state_version + 3
            return result
    first = session.prepare(Revised(), choice.scenario)
    assert first.state.state_version == 4
    session.current = None
    assert session.prepare(Coordinator(), choice.scenario).state.state_version == 5


def test_core_trace_failure_preserves_hosted_usage_without_active_plan(session, choice, ui_root, monkeypatch):
    import project.core.tracing as tracing
    configure(monkeypatch);adapter, client = hosted(choice)
    def fail(*args):raise OSError('private path and sk-secret-trace-error')
    monkeypatch.setattr(tracing, 'save_run', fail)
    assert prepare_plan(session, choice, 'single', 'cp_sat', ui_root, adapter_factory=lambda: adapter) == 'failed'
    assert client.closed and len(client.requests) == 4 and session.core.current is None
    assert len(session.planning_attempt['model_usage']) == 4
    assert 'sk-secret' not in json.dumps(session.planning_attempt)
    assert prepare_plan(session, choice, 'single', 'cp_sat', ui_root, adapter_factory=lambda: adapter) == 'duplicate'


def test_mismatched_coordinator_result_cannot_be_displayed_or_approved(session, choice, ui_root):
    class WrongScenario:
        def __init__(self, *args, **kwargs):pass
        def run(self, scenario, mode, state_version):
            result = Coordinator().run(scenario, mode, state_version=state_version)
            result.state.source_hash = 'different-input'
            return result
    assert prepare_plan(session, choice, 'template', 'cp_sat', ui_root, coordinator_factory=WrongScenario) == 'failed'
    assert session.core.current is None and session.core.approval is None


def test_control_changes_show_old_run_label_without_regenerating(ui_root, monkeypatch):
    monkeypatch.delenv('LLM_MODEL', raising=False)
    at = planning_app(ui_root, monkeypatch)
    at.button(key='generate_plan').click().run()
    run_id = at.session_state[SESSION_KEY].core.current.run_id
    at.selectbox(key='planning_mode').select('single').run()
    assert not at.exception and at.button(key='generate_plan').disabled
    assert at.session_state[SESSION_KEY].core.current.run_id == run_id
    assert any('Controls differ' in element.value for element in at.info)


def test_ui_shows_model_deferral_before_separate_operator_approval(ui_root,choice,monkeypatch):
    configure(monkeypatch);adapter,client=hosted(choice)
    facts=json.dumps({'facts':[f.model_dump() for f in template_facts(choice.scenario)]})
    hold=json.dumps({'finding':'Synthetic action hold for operator review','evidence_ids':['REP-001'],
        'requests':[{'kind':'defer_action','action_ids':['GEN-G1-S02'],'evidence_ids':['REP-001'],
                     'reason':'Fictional test-only inspection requires operator review before allocation.'}]})
    finding=json.dumps({'finding':'Approved policy checked','evidence_ids':['REP-001']})
    review=json.dumps({'decision':'approve','findings':[],'evidence_ids':['REP-001']})
    client.replies=iter([facts,hold,finding,review])
    monkeypatch.setattr(HostedAdapter,'from_env',lambda:adapter)
    at=planning_app(ui_root,monkeypatch)
    at.text_input(key='operator_label').input('Test operator').run()
    at.selectbox(key='planning_mode').select('single').run()
    assert not client.requests
    at.button(key='generate_plan').click().run()
    assert not at.exception and client.closed and len(client.requests)==4
    session=at.session_state[SESSION_KEY]
    assert session.core.current.status=='awaiting_approval' and session.core.approval is None
    assert session.core.current.metadata['decision_effects']
    assert all(a.action_id!='GEN-G1-S02' for a in session.core.current.plan.actions)
    assert any('Agent-requested action deferrals changed this candidate' in w.value for w in at.warning)
    assert not at.button(key='approve_plan').disabled and at.button(key='simulate_plan').disabled


def test_reasoning_setting_changes_hosted_request_identity_only(session,choice,monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv('LLM_REASONING_EFFORT','none')
    single=request_key(session,choice,'single','cp_sat')
    template=request_key(session,choice,'template','cp_sat')
    monkeypatch.setenv('LLM_REASONING_EFFORT','low')
    assert request_key(session,choice,'single','cp_sat')!=single
    assert request_key(session,choice,'template','cp_sat')==template
