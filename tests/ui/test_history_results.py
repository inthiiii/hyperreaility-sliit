"""Read-only history, explicit provenance and safe evaluator-output presentation."""
import csv
import io
import json
from pathlib import Path
from uuid import uuid4

import pytest
from streamlit.testing.v1 import AppTest

from project.core.state import digest
from project.llm.client import HostedAdapter
from project.ui.catalog import load_catalog
from project.ui.history_data import (
    csv_export, filter_history, json_export, linked_simulation, load_history, public_payload, summary_rows,
)
from project.ui.local_records import read_record, save_record
from project.ui.outcome_data import current_outcome, metric_rows, numeric_fields, plot_rows
from project.ui.planning_service import prepare_plan
from project.ui.review_service import record_decision, review_context
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
def case(ui_root):
    catalog = load_catalog(ui_root);choice = catalog.choices[catalog.default_index]
    session = DashboardSession();session.select(choice)
    prepare_plan(session, choice, 'template', 'cp_sat', ui_root)
    return session, choice


def approve(case, root):
    session, choice = case
    record_decision(session, choice, review_context(session, choice)[1], 'approve', 'Test operator', 'Reviewed', root)


def sample_callback(state, plan):
    return {'scenario_id': state.scenario_id, 'plan_id': plan.plan_id, 'state_version': state.state_version,
            'completed_actions': [], 'unmet_needs': ['Test unmet item'],
            'metrics': {'test_missing': None, 'test_zero': 0, 'test_negative': -2},
            'trajectory': [{'tick': 0, 'test_count': 0}, {'tick': 1, 'test_count': None}, {'tick': 2, 'test_count': 2}],
            'run_metadata': {'test_only': True, 'metric_units': {'test_zero': 'test units'},
                'trajectory_plot': {'time_field': 'tick', 'series': ['test_count'], 'time_unit': 'test ticks'}}}


def completed(case, root):
    session, choice = case
    approve(case, root);attach_simulator(session, sample_callback, 'Injected test-only callback')
    assert simulate_approved(session, choice, review_context(session, choice)[1], 'Test operator', root) == 'completed'
    return session.simulation_result


def test_history_loads_all_record_kinds_and_filters_without_state_changes(case, ui_root):
    session, choice = case
    completed(case, ui_root)
    approval_hash = digest(session.core.approval);run_id = session.core.current.run_id
    catalog = load_history(ui_root)
    assert {entry.kind for entry in catalog.entries} == {'run', 'decision', 'simulation', 'attempt'}
    assert not catalog.issues
    assert len(filter_history(catalog, kind='decision')) == 1
    assert not filter_history(catalog, scenario='missing')
    assert len(filter_history(catalog, query=run_id)) == 4
    assert digest(session.core.approval) == approval_hash and session.core.current.run_id == run_id
    assert any(entry.integrity.startswith('Unchecksummed') for entry in catalog.entries)


def test_invalid_tampered_unknown_and_linked_records_are_skipped(case, ui_root, tmp_path):
    base = ui_root / 'results/local_runs'
    target = next(base.glob('*.json'))
    envelope = json.loads(target.read_text());envelope['sha256'] = 'bad';target.write_text(json.dumps(envelope))
    (base / (str(uuid4()) + '.json')).write_text('{bad json')
    (base / 'not-a-record.json').write_text('{}')
    outside = ui_root / 'outside.json';outside.write_text('{}')
    (base / (str(uuid4()) + '.json')).symlink_to(outside)
    catalog = load_history(ui_root)
    assert catalog.issues and not any(entry.kind == 'run' for entry in catalog.entries)


def test_history_byte_and_count_limits_are_explicit(case, ui_root, monkeypatch):
    import project.ui.history_data as history
    monkeypatch.setattr(history, 'MAX_RECORDS', 1)
    catalog = load_history(ui_root)
    assert len(catalog.entries) <= 1 and any('limited' in issue for issue in catalog.issues)
    monkeypatch.setattr(history, 'MAX_TOTAL_BYTES', 1)
    assert any('byte window' in issue for issue in load_history(ui_root).issues)


def test_record_size_limit_and_root_symlink_are_rejected(case, ui_root, monkeypatch):
    import project.ui.history_data as history
    monkeypatch.setattr(history, 'MAX_BYTES', 10)
    assert not load_history(ui_root).entries
    base = ui_root / 'results/local_runs';moved = ui_root / 'moved-records'
    base.rename(moved);base.symlink_to(moved, target_is_directory=True)
    assert not load_history(ui_root).entries


def test_failed_usage_is_unknown_not_zero(case, ui_root):
    session, choice = case
    path = next((ui_root / 'results/local_runs/ui_attempts').glob('*.json'))
    payload = json.loads(path.read_text());payload['status'] = 'failed';payload['model_usage'] = [{'status': 'error'}]
    path.write_text(json.dumps(payload))
    entry = next(entry for entry in load_history(ui_root).entries if entry.kind == 'attempt')
    row = summary_rows([entry])[0]
    assert row['Model calls'] == 1 and row['Reported input tokens'] is None and row['Reported output tokens'] is None


def test_exports_filter_hidden_truth_credentials_and_csv_formulas():
    payload = {'api_key': 'secret', 'ground_truth': {'answer': 1}, 'future_events': ['private'],
               'nested': {'hidden_world': 2, 'safe': 'Bearer private-token sk-example'}, 'safe': 3}
    exported = json.loads(json_export(payload))
    assert 'ground_truth' not in exported and 'future_events' not in exported
    assert 'hidden_world' not in exported['nested'] and exported['safe'] == 3
    assert 'private-token' not in json_export(payload) and exported['api_key'] == '[REDACTED]'
    rows = list(csv.reader(io.StringIO(csv_export([{'=badheader': '=HYPERLINK("bad")', 'number': -2, 'empty': None}]))))
    assert rows[0][0].startswith("'") and rows[1][0].startswith("'")
    assert rows[1][1] == '-2' and rows[1][2] == ''


def test_historical_result_requires_matching_run_and_approval(case, ui_root):
    completed(case, ui_root)
    catalog = load_history(ui_root);entry = next(entry for entry in catalog.entries if entry.kind == 'simulation')
    simulation, issue = linked_simulation(entry, catalog)
    assert simulation is not None and issue is None
    from dataclasses import replace
    without = replace(catalog, entries=tuple(item for item in catalog.entries if item.kind != 'decision'))
    assert linked_simulation(entry, without)[0] is None
    entry.payload['binding'] = 'wrong'
    assert linked_simulation(entry, catalog)[0] is None


def test_current_result_must_match_current_plan_and_state(case, ui_root):
    session, choice = case
    assert current_outcome(session) == (None, None)
    completed(case, ui_root)
    assert current_outcome(session)[0] is not None
    session.core.current.plan.explanation += ' changed'
    assert current_outcome(session)[0] is None and current_outcome(session)[1]


def test_metrics_preserve_null_zero_negative_and_explicit_units(case, ui_root):
    result = completed(case, ui_root)
    rows = {row['Metric']: row for row in metric_rows(result)}
    assert rows['test_missing']['Value'] is None
    assert rows['test_zero']['Value'] == 0 and rows['test_zero']['Unit'] == 'test units'
    assert rows['test_negative']['Value'] == -2 and rows['test_negative']['Unit'] == 'Not specified'


def test_plot_mapping_preserves_null_and_rejects_ambiguous_time():
    rows = [{'tick': 0, 'value': 1}, {'tick': 1, 'value': None}, {'tick': 2, 'value': 3}]
    assert numeric_fields(rows) == ['tick', 'value']
    assert plot_rows(rows, 'tick', ['value'])[1]['Value'] is None
    with pytest.raises(ValueError):plot_rows(rows, 'missing', ['value'])
    with pytest.raises(ValueError):plot_rows([{'tick': 1, 'value': 2}, {'tick': 1, 'value': 3}], 'tick', ['value'])
    assert 'flag' not in numeric_fields([{'flag': True}])


def test_nonfinite_nested_output_cannot_be_saved_or_accepted(case, ui_root):
    session, choice = case;approve(case, ui_root)
    def bad(state, plan):
        output = sample_callback(state, plan);output['trajectory'][0]['test_count'] = float('inf');return output
    attach_simulator(session, bad, 'Injected invalid callback')
    assert simulate_approved(session, choice, review_context(session, choice)[1], 'Test operator', ui_root) == 'failed'
    assert session.simulation_result is None


def app(ui_root, monkeypatch):
    monkeypatch.setenv('RELINK_HISTORY_TEST_ROOT', str(ui_root))
    def forbidden(*args, **kwargs):raise AssertionError('History/results must never construct a model client')
    monkeypatch.setattr(HostedAdapter, '__init__', forbidden)
    script = '''
import os
from project.ui.app import render_app
render_app(os.environ['RELINK_HISTORY_TEST_ROOT'])
'''
    return AppTest.from_string(script, default_timeout=20).run()


def test_history_ui_loads_saved_run_without_rehydrating_or_inference(case, ui_root, monkeypatch):
    session, choice = case;approve(case, ui_root)
    at = app(ui_root, monkeypatch)
    assert at.session_state[SESSION_KEY].core.current is None
    at.radio(key='workspace_page').set_value('History').run()
    assert not at.exception and at.selectbox(key='history_record')
    at.selectbox(key='history_kind').select('run').run()
    assert not at.exception and at.session_state[SESSION_KEY].core.current is None
    assert at.session_state[SESSION_KEY].core.approval is None
    at.text_input(key='history_query').input('not-present').run()
    assert not at.exception and any('No records match' in item.value for item in at.info)


def test_history_can_be_read_after_scenario_files_are_removed(case, ui_root, monkeypatch):
    for path in (ui_root / 'tests/core/fixtures').glob('*.json'):path.unlink()
    at = app(ui_root, monkeypatch);at.radio(key='workspace_page').set_value('History').run()
    assert not at.exception and at.selectbox(key='history_record')


def test_results_empty_state_has_no_fabricated_metric_cards(ui_root, monkeypatch):
    at = app(ui_root, monkeypatch);at.radio(key='workspace_page').set_value('Results').run()
    assert not at.exception and not at.metric
    assert any('No simulation results' in item.value for item in at.subheader)


def test_test_outcome_ui_renders_metrics_plot_and_provenance(case, ui_root, monkeypatch):
    result = completed(case, ui_root)
    at = app(ui_root, monkeypatch)
    # This is an explicitly injected test session, never an application-installed simulator.
    at.session_state[SESSION_KEY] = case[0]
    at.radio(key='workspace_page').set_value('Results').run()
    assert not at.exception
    assert any('TEST OUTPUT' in item.value for item in at.warning)
    assert any('Unavailable' in str(item.value) for item in at.dataframe)
    assert at.selectbox(key='current_' + result.plan_id + '_time').value == 'tick'
    assert at.multiselect(key='current_' + result.plan_id + '_series').value == ['test_count']
    run_id = case[0].core.current.run_id
    at.radio(key='workspace_page').set_value('History').run()
    at.selectbox(key='history_kind').select('simulation').run()
    assert not at.exception and at.session_state[SESSION_KEY].core.current.run_id == run_id
    assert any('TEST OUTPUT' in item.value for item in at.warning)


def test_hosted_attempt_metadata_remains_visible_and_strict(case, ui_root):
    path = next((ui_root / 'results/local_runs/ui_attempts').glob('*.json'))
    payload = json.loads(path.read_text())
    payload.update(configured_api_mode='responses', configured_reasoning_effort='none',
                   auxiliary_requests=[{'operation': 'input_count', 'status': 'completed'}])
    path.write_text(json.dumps(payload))
    catalog = load_history(ui_root)
    assert any(e.kind == 'attempt' and e.payload['attempt_id'] == payload['attempt_id'] for e in catalog.entries)
    payload['auxiliary_requests'] = 'malformed'
    path.write_text(json.dumps(payload))
    assert not any(e.kind == 'attempt' for e in load_history(ui_root).entries)
    payload['auxiliary_requests'] = []
    payload['unexpected_field'] = True
    path.write_text(json.dumps(payload))
    assert not any(e.kind == 'attempt' for e in load_history(ui_root).entries)
