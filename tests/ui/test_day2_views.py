"""Map, crew Gantt, agent conversation, operator inbox and field work (no live API)."""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'core'))  # FakeClient helper

import pytest
from streamlit.testing.v1 import AppTest

from project.auth import PermissionDenied, User
from project.core.orchestrator import AgentOrchestrator
from project.data.loader import CaseLoader
from project.llm.client import HostedAdapter
from project.ui import map_view as M
from project.ui.agent_view import collaboration_counts, conversation_rows, gantt_rows, inbox
from project.ui.priority_service import record_priority_decision
from project.ui.session import DashboardSession, SESSION_KEY

ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / 'releases' / 'evidence-v3-20261126'
LOADER = CaseLoader(V3 / 'data' / 'processed' / 'agent_inputs')
MANAGER = User('mgr', 'Manager One', 'restoration_manager')
COORDINATOR = User('coord', 'Coordinator One', 'noc_coordinator')


def case(cid='DEV-001'):
    return LOADER.load_case(LOADER.find(cid))


def fake_multi_run(cid='DEV-001'):
    from test_models import FakeClient
    truth = json.loads((V3 / 'data/evaluation/ground_truth/development' / f'{cid}.json').read_text())
    facts = [{'target_type': l['target_type'], 'target_id': l['target_id'], 'attribute': l['attribute'],
              'value': l['reported_value'], 'evidence_ids': [l['report_id']], 'observed_at_min': None,
              'received_at_min': None, 'status': 'unverified', 'reason': ''} for l in truth['expected_report_facts']]
    wrong = [dict(facts[0], target_id='S02')]
    injection = [d['report_id'] for d in truth['distractor_reports'] if d['kind'] == 'prompt_injection']
    s = case(cid)
    proposal = {'service_id': s.services[0].service_id, 'proposed_critical': True,
                'evidence_ids': [s.reports[0].report_id], 'reason': 'Field note mentions a clinic'}
    replies = [
        json.dumps({'facts': wrong, 'ignored_reports': [{'report_id': r, 'kind': 'instruction_attempt', 'note': 'override'}
                                                         for r in injection], 'finding': 'x'}),
        json.dumps({'finding': 'Crews ok', 'evidence_ids': [], 'requests': [],
                    'questions': [{'target_id': 'S03', 'question': 'Is the S03 road passable?', 'evidence_ids': []}],
                    'priority_proposals': []}),
        json.dumps({'finding': 'Weights applied', 'evidence_ids': [], 'requests': [], 'questions': [],
                    'priority_proposals': [proposal]}),
        json.dumps({'decision': 'revise', 'fact_challenges': [{'report_id': facts[0]['evidence_ids'][0], 'target_id': 'S02',
                    'attribute': facts[0]['attribute'], 'problem': 'Code belongs to another site'}], 'requests': [],
                    'findings': ['wrong site'], 'evidence_ids': []}),
        json.dumps({'facts': facts, 'ignored_reports': [], 'finding': 'corrected'}),
        json.dumps({'decision': 'approve', 'fact_challenges': [], 'requests': [], 'findings': [], 'evidence_ids': []}),
    ]
    adapter = HostedAdapter('openai', 'fake-model', 'fake-key', client=FakeClient(replies))
    return AgentOrchestrator(adapter).run(s, 'multi')


def test_map_rows_use_town_coordinates_and_status_colours():
    s = case('DEMO-005')
    rows = M.layer_rows(s)
    assert len(rows['sites']) == len(s.sites) and all(6.4 < r['lat'] < 7.3 and 79.8 < r['lon'] < 80.3 for r in rows['sites'])
    assert {r['status'] for r in rows['sites']} <= {'OK', 'Fault', 'Unknown'}
    assert len(rows['links']) == len(s.links) and len(rows['roads']) == len(s.roads)
    assert all(r['label'].startswith(x.label) for r, x in zip(rows['sites'], s.sites))


def test_map_falls_back_to_grid_for_legacy_cases():
    legacy = CaseLoader(ROOT / 'data/processed/agent_inputs').load_case('demo/DEMO-005.json')
    pos = M.positions(legacy)
    assert all(M.LAT_RANGE[0] <= lat <= M.LAT_RANGE[1] for lat, _ in pos.values() if (lat, _) not in (M.CORE_POINT, M.DEPOT_POINT))


def test_replay_reads_simulator_availability_and_crew_positions():
    trajectory = [{'t': 0, 'type': 'availability', 'available_services': []},
                  {'t': 30, 'type': 'availability', 'available_services': ['V01']}]
    assert M.available_at(trajectory, 10) == set() and M.available_at(trajectory, 30) == {'V01'}
    result = fake_multi_run()
    rows = M.layer_rows(result.state.scenario, trajectory=trajectory, minute=30, plan=result.plan)
    assert {r['status'] for r in rows['sites']} <= {'Up', 'Down', 'Not served'}
    assert rows['crews'] and all('doing' in c for c in rows['crews'])


def test_gantt_conversation_and_inbox_from_a_real_orchestrator_run():
    result = fake_multi_run()
    assert result.status == 'awaiting_approval'
    lanes = {r['Lane'] for r in gantt_rows(result)}
    assert lanes and all(l.startswith(('Crew', 'Generator')) for l in lanes)
    rows = conversation_rows(result)
    kinds = [r['Kind'] for r in rows]
    assert {'Extraction', 'Shared facts', 'Specialist finding', 'Schedule', 'Challenge', 'Review'} <= set(kinds)
    challenge = next(r for r in rows if r['Kind'] == 'Challenge')
    assert challenge['From'] == 'Plan Reviewer' and challenge['To'] == 'Network Investigator'
    assert any('instruction attempt flagged' in r['Summary'] for r in rows)
    counts = collaboration_counts(result)
    assert counts['agents'] == 4 and counts['challenges'] == 1 and counts['schedules'] == 2
    box = inbox(result)
    assert box['questions'] and box['proposals'][0]['status'] == 'pending_human_decision'


def test_priority_decision_requires_manager_and_is_audited(tmp_path):
    result = fake_multi_run()
    session = DashboardSession()
    with pytest.raises(PermissionDenied):
        record_priority_decision(session, result, 0, 'accept', '', tmp_path, user=COORDINATOR)
    assert record_priority_decision(session, result, 0, 'accept', 'agreed', tmp_path, user=MANAGER) == 'accept'
    assert record_priority_decision(session, result, 0, 'reject', '', tmp_path, user=MANAGER) == 'duplicate'
    saved = list((tmp_path / 'results/local_runs/priority_decisions').glob('*.json'))
    payload = json.loads(saved[0].read_text())['payload']
    assert payload['username'] == 'mgr' and 'unchanged' in payload['effect']
    assert result.state.scenario.services == case().services  # policy for this incident untouched


@pytest.fixture
def v3_root(tmp_path):
    target = tmp_path / 'releases/evidence-v3-20261126/data'
    shutil.copytree(V3 / 'data', target)
    return tmp_path


@pytest.mark.parametrize('page', ['Map', 'Field work', 'Planning', 'Incident'])
def test_new_pages_render_on_v3_cases(v3_root, monkeypatch, page):
    monkeypatch.setenv('RELINK_DAY2_ROOT', str(v3_root))
    at = AppTest.from_string("import os\nfrom project.ui.app import render_app\nrender_app(os.environ['RELINK_DAY2_ROOT'])",
                             default_timeout=30).run()
    at.radio(key='workspace_page').set_value(page).run()
    assert not at.exception
    if page == 'Map':
        assert any('Fictional sites placed in real' in c.value for c in at.caption)
    if page == 'Field work':
        assert any('No approved plan' in i.value for i in at.info)


def test_inbox_tab_renders_for_a_recorded_run(v3_root, monkeypatch):
    monkeypatch.setenv('RELINK_DAY2_ROOT', str(v3_root))
    at = AppTest.from_string("import os\nfrom project.ui.app import render_app\nrender_app(os.environ['RELINK_DAY2_ROOT'])",
                             default_timeout=30).run()
    at.radio(key='workspace_page').set_value('Planning').run()
    session = at.session_state[SESSION_KEY]
    result = fake_multi_run('DEV-001')
    choice = next(c for c in __import__('project.ui.catalog', fromlist=['load_catalog']).load_catalog(v3_root).choices
                  if c.scenario.scenario_id == 'DEV-001')
    at.selectbox(key='scenario_picker').set_value(choice.key).run()
    session = at.session_state[SESSION_KEY]
    session.core.current = result.model_copy(update={'state': result.state.model_copy(update={'source_hash': choice.content_hash})})
    at.run()
    assert not at.exception
    assert any(t.label.startswith('Operator inbox') for t in at.tabs)
    assert any('Accept as policy request' == b.label for b in at.button)
