"""Plan export, inline answers, what-if, scenario upload and approval notifications."""
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'core'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from project.auth import PermissionDenied, User
from project.data.evaluator import EvaluatorLoader
from project.ui import notifications as N
from project.ui.catalog import load_catalog
from project.ui.inbox_answer import label, relevant_options
from project.ui.plan_export import build_summary, pdf_bytes, text_summary
from project.ui.session import SESSION_KEY
from project.ui.upload_service import UploadRejected, check_upload, remove_upload, save_upload
from project.ui.whatif import compare, disrupt, has_truth

ROOT = Path(__file__).resolve().parents[2]
V3 = 'releases/evidence-v3-20261126'
TRUTH = ROOT / V3 / 'data/evaluation/ground_truth'
COORD = User('coordinator', 'Coordinator', 'noc_coordinator')
MANAGER = User('manager', 'Manager', 'restoration_manager')


def multi_run():
    from test_day2_views import fake_multi_run
    return fake_multi_run('DEV-001')


# ------------------------------------------------------------------ 1. plan export
def test_plan_summary_pdf_has_jobs_reasons_approval_and_result():
    from project.core.coordinator import approve
    from project.simulation.episode import IncidentEpisode
    r = multi_run()
    approval = approve(r.plan.plan_id, r.state.state_version, 'approve', plan=r.plan, state=r.state, operator_id='Manager')
    sim = IncidentEpisode(r.state.scenario, EvaluatorLoader(TRUTH).load('DEV-001')).advance(
        r.state.scenario, r.plan, approval, state=r.state)
    summary = build_summary(r, SimpleNamespace(approval=approval, note='Looks right'), sim,
                            {'weighted_downtime_min': sim.metrics['weighted_downtime_min'] + 100})
    assert [j['job'] for j in summary['jobs']] == [a.action_id for a in r.plan.actions]
    assert any(who == 'Plan Reviewer' for who, _ in summary['reasons'])
    assert ('Note', 'Looks right') in summary['approval'] and summary['result'] and summary['comparison']
    assert pdf_bytes(summary).startswith(b'%PDF') and 'Approval:' in text_summary(summary)
    empty = build_summary(r)
    assert empty['approval'] is None and empty['result'] is None and pdf_bytes(empty).startswith(b'%PDF')


# ------------------------------------------------------------------ 2. inline answers
def test_answer_options_focus_on_the_question_target():
    r = multi_run()
    options = relevant_options(r.state.scenario, 'S03')
    assert options and all(v[1] == 'S03' for v in options.values())
    assert label(next(iter(options))).startswith('S03 · ')
    assert len(relevant_options(r.state.scenario, 'unknown-thing')) > len(options)


# ------------------------------------------------------------------ 3. what-if
def test_whatif_crew_loss_breaks_the_current_plan_and_replans_without_touching_it():
    r = multi_run()
    before = r.plan.model_dump_json()
    crew = r.plan.actions[0].crew_id
    out = compare(r, {crew: 720}, (), truth=EvaluatorLoader(TRUTH).load('DEV-001'))
    current, kept, replanned = out['rows']
    assert current['valid'] and not kept['valid'] and replanned['valid']
    assert all(job[0] != crew for job in out['added'])
    assert 'weighted_downtime_min' in current['measured'] and 'weighted_downtime_min' in replanned['measured']
    assert r.plan.model_dump_json() == before


def test_whatif_road_closure_is_applied_to_plan_and_simulator():
    r = multi_run()
    road = next(iter(r.state.scenario.observed_state.roads))
    world, truth = disrupt(r.state, {}, [road], EvaluatorLoader(TRUTH).load('DEV-001'))
    assert world.resolved_observations.roads[road] is False and truth.roads[road] is False
    assert r.state.resolved_observations.roads[road] is not False or r.state.scenario.observed_state.roads[road] is False
    assert has_truth(SimpleNamespace(key=f'{V3}/data/processed/agent_inputs/demo/DEMO-005.json'))
    assert not has_truth(SimpleNamespace(key='.relink/uploads/MY-1.json'))


# ------------------------------------------------------------------ 4. upload
def _visible(case='DEMO-005'):
    return json.loads((ROOT / V3 / 'data/processed/agent_inputs/demo' / f'{case}.json').read_text())


def test_upload_rules(tmp_path):
    data = _visible()
    with pytest.raises(UploadRejected, match='already exists'):
        check_upload(json.dumps(data).encode(), ['DEMO-005'])
    with pytest.raises(UploadRejected, match='not valid JSON'):
        check_upload(b'{nope', [])
    with pytest.raises(UploadRejected, match='Not a valid incident'):
        check_upload(json.dumps(dict(data, ground_truth={'x': 1})).encode(), [])
    data['scenario_id'] = 'MY-STORM-1'
    with pytest.raises(PermissionDenied):
        save_upload(tmp_path, json.dumps(data).encode(), [], MANAGER)
    key = save_upload(tmp_path, json.dumps(data).encode(), [], COORD)
    assert key == '.relink/uploads/MY-STORM-1.json' and (tmp_path / key).is_file()
    choice = next(c for c in load_catalog(tmp_path).choices if c.scenario.scenario_id == 'MY-STORM-1')
    assert choice.source == 'uploaded' and choice.label.endswith('· uploaded')
    remove_upload(tmp_path, key, COORD)
    assert not (tmp_path / key).exists()
    with pytest.raises(UploadRejected):
        remove_upload(tmp_path, f'{V3}/data/processed/agent_inputs/demo/DEMO-005.json', COORD)


# ------------------------------------------------------------------ 5. notifications
def test_notifications_follow_role_and_plan_state(monkeypatch):
    r = multi_run()
    choice = SimpleNamespace(content_hash=r.state.source_hash)
    session = SimpleNamespace(core=SimpleNamespace(current=r), last_decision=None, simulation_result=None)
    monkeypatch.setattr(N, 'active_approval', lambda s, c: False)
    field = User('field', 'Field', 'field_supervisor')
    assert ('Planning', 'A plan is waiting for your approval') in N.notifications(session, choice, MANAGER)
    coord = N.notifications(session, choice, COORD)
    assert ('Planning', 'Plan sent: waiting for a Restoration Manager') in coord
    assert any('agent question' in msg for _, msg in coord)
    monkeypatch.setattr(N, 'active_approval', lambda s, c: True)
    assert N.notifications(session, choice, MANAGER) == [('Planning', 'Approved plan ready to simulate')]
    assert N.notifications(session, choice, field) == [('Field work', '1 job assigned in the approved plan')]
    session.last_decision = SimpleNamespace(approval=SimpleNamespace(plan_id=r.plan.plan_id, decision='reject'))
    monkeypatch.setattr(N, 'active_approval', lambda s, c: False)
    assert ('Planning', 'Plan rejected: revise and generate again') in N.notifications(session, choice, COORD)
    assert N.badge_counts([('Planning', 'a'), ('Planning', 'b'), ('Field work', 'c')]) == {'Planning': 2, 'Field work': 1}


# ------------------------------------------------------------------ app wiring
@pytest.fixture
def app_root(tmp_path):
    # Original template-parsable data: the offline template produces a plan on it.
    for part in ('processed/agent_inputs/demo', 'evaluation/ground_truth/demo'):
        shutil.copytree(ROOT / 'data' / part, tmp_path / 'data' / part)
    return tmp_path


def app(root, monkeypatch):
    monkeypatch.setenv('RELINK_DAY5_ROOT', str(root))
    return AppTest.from_string("import os\nfrom project.ui.app import render_app\nrender_app(os.environ['RELINK_DAY5_ROOT'])",
                               default_timeout=60).run()


def test_app_whatif_upload_and_export_pages(app_root, monkeypatch):
    at = app(app_root, monkeypatch)
    at.radio(key='workspace_page').set_value('What-if').run()
    assert not at.exception and any('Generate a plan first' in i.value for i in at.info)
    at.radio(key='workspace_page').set_value('Planning').run()
    at.button(key='generate_plan').click().run()
    assert not at.exception and at.session_state[SESSION_KEY].core.current.plan is not None
    at.radio(key='workspace_page').set_value('What-if').run()
    crew = at.session_state[SESSION_KEY].core.current.state.scenario.crews[0].crew_id
    at.slider(key=f'whatif_crew_{crew}').set_value(720).run()
    at.button(key='whatif_run').click().run()
    assert not at.exception and any(d.value is not None for d in at.dataframe)
    at.radio(key='workspace_page').set_value('Results').run()
    assert not at.exception and any(e.value == 'Plan summary' for e in at.subheader)
    assert at.button(key='upload_add')


def test_answering_an_unknown_in_the_inbox_records_evidence_and_replans(tmp_path, monkeypatch):
    shutil.copytree(ROOT / V3 / 'data', tmp_path / V3 / 'data')
    at = app(tmp_path, monkeypatch)
    at.radio(key='workspace_page').set_value('Planning').run()
    at.button(key='generate_plan').click().run()
    first = at.session_state[SESSION_KEY].core.current
    assert first.status == 'escalated' and first.state.unresolved_facts
    from project.ui.agent_view import inbox
    questions = inbox(first)['questions']
    assert questions and all(q['fact'] for q in questions)
    from project.ui.inbox_answer import form_id
    fid = form_id(questions[0])
    at.radio(key=f'answer_value_{fid}').set_value('No: failed / unavailable / closed')
    at.text_input(key=f'answer_source_{fid}').input('Phone call with the field team')
    at.checkbox(key=f'answer_ack_{fid}').check()
    next(b for b in at.button if b.label == 'Record answer and replan').click().run()
    session = at.session_state[SESSION_KEY]
    assert not at.exception and len(session.confirmation_history) == 1
    again = session.core.current
    assert again is not None and again.run_id != first.run_id
    assert len(again.state.unresolved_facts) == len(first.state.unresolved_facts) - 1
    nxt = form_id(inbox(again)['questions'][0])
    assert at.checkbox(key=f'answer_ack_{nxt}').value is False
