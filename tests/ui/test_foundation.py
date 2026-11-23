"""Behavioral checks for data isolation, session safety and Streamlit reruns."""
import json
from dataclasses import replace
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from project.core.state import digest
from project.llm.client import HostedAdapter
from project.ui.catalog import load_catalog
from project.ui.session import DashboardSession, SESSION_KEY, get_dashboard_session

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/core/fixtures/DEMO-005.json'


@pytest.fixture
def fixture_root(tmp_path):
    target = tmp_path / 'tests/core/fixtures'
    target.mkdir(parents=True)
    for source in (ROOT / 'tests/core/fixtures').glob('*.json'):
        (target / source.name).write_bytes(source.read_bytes())
    return tmp_path


def publish(root, relative, payload=None):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(FIXTURE.read_text() if payload is None else json.dumps(payload))
    return path


def test_fallback_is_explicit_and_default_is_demo(fixture_root):
    catalog = load_catalog(fixture_root)
    assert catalog.using_fixtures
    assert len(catalog.choices) == 6
    assert catalog.choices[catalog.default_index].scenario.scenario_id == 'DEMO-005'
    assert all(choice.source == 'development_fixture' for choice in catalog.choices)


def test_processed_input_replaces_fixtures_but_never_lists_evaluation(tmp_path):
    publish(tmp_path, 'data/processed/agent_inputs/demo/case.json')
    publish(tmp_path, 'data/processed/agent_inputs/candidate_evaluation/answer.json')
    publish(tmp_path, 'data/evaluation/ground_truth/answer.json')
    publish(tmp_path, 'data/raw/synthetic/answer.json')
    publish(tmp_path, 'tests/core/fixtures/DEMO-005.json')
    catalog = load_catalog(tmp_path)
    assert len(catalog.choices) == 1 and not catalog.using_fixtures
    assert catalog.choices[0].source == 'processed_input'
    assert catalog.choices[0].key == 'data/processed/agent_inputs/demo/case.json'


def test_reject_hidden_truth_without_echoing_its_contents(tmp_path):
    payload = json.loads(FIXTURE.read_text());payload['ground_truth'] = 'private evaluator answer'
    publish(tmp_path, 'data/processed/agent_inputs/demo/invalid.json', payload)
    publish(tmp_path, 'tests/core/fixtures/DEMO-005.json')
    catalog = load_catalog(tmp_path)
    assert catalog.using_fixtures and catalog.issues
    assert 'private evaluator answer' not in str(catalog.issues)


def test_symlink_escape_is_not_read(tmp_path):
    target = publish(tmp_path, 'data/evaluation/ground_truth/answer.json')
    directory = tmp_path / 'data/processed/agent_inputs/demo';directory.mkdir(parents=True)
    (directory / 'escape.json').symlink_to(target)
    assert not load_catalog(tmp_path).choices


def test_directory_symlink_cannot_import_evaluator_data(tmp_path):
    target = publish(tmp_path, 'data/evaluation/ground_truth/answer.json')
    link = tmp_path / 'data/processed/agent_inputs/demo';link.parent.mkdir(parents=True)
    link.symlink_to(target.parent, target_is_directory=True)
    assert not load_catalog(tmp_path).choices


def test_duplicate_invalid_and_oversized_cases_are_reported(tmp_path):
    publish(tmp_path, 'data/processed/agent_inputs/demo/a.json')
    publish(tmp_path, 'data/processed/agent_inputs/demo/b.json')
    invalid = publish(tmp_path, 'data/processed/agent_inputs/demo/c.json');invalid.write_text('{invalid')
    oversized = publish(tmp_path, 'data/processed/agent_inputs/demo/d.json');oversized.write_text(' ' * 2_000_001)
    catalog = load_catalog(tmp_path)
    assert len(catalog.choices) == 1 and len(catalog.issues) == 3


def test_same_selection_preserves_state_but_content_change_revokes_results(fixture_root):
    choice = load_catalog(fixture_root).choices[0]
    session = DashboardSession();assert session.select(choice)
    old_core = session.core
    session.core.current = object();session.core.approval = object();session.simulation_result = object()
    assert not session.select(choice) and session.core is old_core
    scenario = choice.scenario.model_copy(deep=True);scenario.region_label += ' revised'
    changed = replace(choice, scenario=scenario, content_hash=digest(scenario))
    assert session.select(changed) and session.selection_revision == 2
    assert session.core.current is None and session.core.approval is None and session.simulation_result is None


def test_sessions_are_isolated_and_empty_catalog_clears_state(fixture_root):
    first = {};second = {}
    a = get_dashboard_session(first);b = get_dashboard_session(second)
    assert get_dashboard_session(first) is a and a.core is not b.core
    a.select(load_catalog(fixture_root).choices[0]);a.simulation_result = object()
    assert a.clear_selection() and a.selected_key is None and a.simulation_result is None
    assert not a.clear_selection()


def app(monkeypatch, fixture_root):
    import project.ui.app as views
    monkeypatch.setattr(views, 'load_catalog', lambda root: load_catalog(fixture_root))
    def forbidden(*args, **kwargs):
        raise AssertionError('Browsing must never construct a hosted adapter or make inference requests')
    monkeypatch.setattr(HostedAdapter, '__init__', forbidden)
    monkeypatch.setattr(HostedAdapter, 'complete', forbidden)
    return AppTest.from_file(ROOT / 'project/main.py', default_timeout=15).run()


def test_navigation_and_reruns_preserve_session_without_api_calls(monkeypatch, fixture_root):
    at = app(monkeypatch, fixture_root)
    assert not at.exception
    session_id = at.session_state[SESSION_KEY].session_id
    core = at.session_state[SESSION_KEY].core
    assert at.selectbox(key='scenario_picker').value.endswith('DEMO-005.json')
    for page in ('Incident', 'Planning', 'Results', 'Settings', 'Overview'):
        at.radio(key='workspace_page').set_value(page).run()
        assert not at.exception
        assert at.session_state[SESSION_KEY].session_id == session_id
        assert at.session_state[SESSION_KEY].core is core
        assert all(button.disabled for button in at.button if button.key != 'generate_plan')
        assert at.session_state[SESSION_KEY].core.current is None
    at.text_input(key='operator_label').input('Test operator').run()
    assert at.session_state[SESSION_KEY].session_id == session_id
    assert at.session_state[SESSION_KEY].core.current is None


def test_scenario_change_invalidates_old_session_outputs(monkeypatch, fixture_root):
    at = app(monkeypatch, fixture_root)
    session = at.session_state[SESSION_KEY]
    session.core.current = object();session.core.approval = object();session.simulation_result = object()
    at.selectbox(key='scenario_picker').select('tests/core/fixtures/DEV-004.json').run()
    assert not at.exception
    session = at.session_state[SESSION_KEY]
    assert session.selection_revision == 2
    assert session.core.current is None and session.core.approval is None and session.simulation_result is None


def test_settings_never_displays_api_secret(monkeypatch, fixture_root):
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-local-must-not-render')
    monkeypatch.setenv('LLM_MODEL', 'test-model')
    at = app(monkeypatch, fixture_root);at.radio(key='workspace_page').set_value('Settings').run()
    assert not at.exception
    assert 'sk-local-must-not-render' not in str(at)
    assert any('unverified' in element.value for element in at.success)


def test_empty_catalog_renders_help_without_crashing(tmp_path,monkeypatch):
    monkeypatch.setenv('RELINK_TEST_ROOT', str(tmp_path))
    script = '''
import os
from project.ui.app import render_app
render_app(os.environ['RELINK_TEST_ROOT'])
'''
    at = AppTest.from_string(script, default_timeout=15).run()
    assert not at.exception and at.error
    assert at.session_state[SESSION_KEY].selected_key is None


def test_visible_file_change_invalidates_outputs_on_rerun(monkeypatch, fixture_root):
    at = app(monkeypatch, fixture_root)
    session = at.session_state[SESSION_KEY]
    session.core.current = object();session.core.approval = object();session.simulation_result = object()
    path = fixture_root / 'tests/core/fixtures/DEMO-005.json'
    payload = json.loads(path.read_text());payload['region_label'] += ' corrected'
    path.write_text(json.dumps(payload))
    at.run()
    assert not at.exception
    session = at.session_state[SESSION_KEY]
    assert session.selection_revision == 2 and session.core.current is None
    assert session.core.approval is None and session.simulation_result is None


def test_removed_selected_file_reselects_safely(monkeypatch, fixture_root):
    at = app(monkeypatch, fixture_root)
    (fixture_root / 'tests/core/fixtures/DEMO-005.json').unlink()
    at.run()
    assert not at.exception
    assert at.selectbox(key='scenario_picker').value.endswith('DEV-004.json')
    assert at.session_state[SESSION_KEY].selection_revision == 2
