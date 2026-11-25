"""Benchmark page, no-AI comparison, step-by-step Planning, live agent feed and map routes."""
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'core'))  # FakeClient helper

from project.core.orchestrator import AgentOrchestrator
from project.ui import map_view as M
from project.ui.agent_view import LiveFeed
from project.ui.baseline_compare import ai_measured, simulate_no_ai
from project.ui.benchmark_page import available_runs, load_run, per_case_long

ROOT = Path(__file__).resolve().parents[2]
V3 = 'releases/evidence-v3-20261126'
RUN = ROOT / 'results/final/evaluation-v3-run1'


@pytest.fixture
def app_root(tmp_path):
    shutil.copytree(ROOT / V3 / 'data', tmp_path / V3 / 'data')
    out = tmp_path / 'results/final/evaluation-v3-run1'
    out.mkdir(parents=True)
    for name in ('summary_report.json', 'per_case.csv', 'README.md'):
        shutil.copy(RUN / name, out / name)
    return tmp_path


def app(root, monkeypatch):
    monkeypatch.setenv('RELINK_DAY4_ROOT', str(root))
    return AppTest.from_string("import os\nfrom project.ui.app import render_app\nrender_app(os.environ['RELINK_DAY4_ROOT'])",
                               default_timeout=40).run()


def test_benchmark_data_comes_from_result_files(app_root):
    runs = available_runs(app_root)
    assert [p.name for p in runs] == ['evaluation-v3-run1']
    summary, rows = load_run(runs[0])
    assert summary['cases'] == 20 and len(rows) == 20
    long = per_case_long(rows, ['multi', 'optimizer'])
    assert len(long) == 40 and {r['Variant'] for r in long} == {'Multi-agent', 'CP-SAT (no AI)'}


def test_benchmark_page_renders_headlines_without_a_scenario(app_root, monkeypatch):
    at = app(app_root, monkeypatch)
    at.radio(key='workspace_page').set_value('Benchmark').run()
    assert not at.exception
    text = ' '.join(m.value for m in at.markdown)
    assert 'Agents vs no AI' in text and 'Multi-agent vs single agent' in text and 'Reviewer' in text
    assert any('Interval includes zero' in c.value for c in at.caption)


def test_no_benchmark_results_is_an_empty_state(tmp_path, monkeypatch):
    shutil.copytree(ROOT / V3 / 'data', tmp_path / V3 / 'data')
    at = app(tmp_path, monkeypatch)
    at.radio(key='workspace_page').set_value('Benchmark').run()
    assert not at.exception and any('No benchmark results' in i.value for i in at.info)


def test_no_ai_comparison_matches_benchmark_baseline_and_handles_replanning(app_root):
    rows = {r['case']: r for r in load_run(app_root / 'results/final/evaluation-v3-run1')[1]}
    out = simulate_no_ai(app_root, f'{V3}/data/processed/agent_inputs/candidate_evaluation/EVAL2-001.json')
    assert out['weighted_downtime_min'] == float(rows['EVAL2-001']['optimizer_median_downtime'])
    event_case = simulate_no_ai(app_root, f'{V3}/data/processed/agent_inputs/development/DEV-010.json')
    assert event_case['weighted_downtime_min'] > 0


def test_comparison_only_offered_after_a_complete_simulation():
    partial = SimpleNamespace(simulation_result=SimpleNamespace(run_metadata={'measurement_scope': 'elapsed_prefix'},
                                                                metrics={'weighted_downtime_min': 1}))
    complete = SimpleNamespace(simulation_result=SimpleNamespace(run_metadata={'measurement_scope': 'complete_incident'},
                                                                 metrics={'weighted_downtime_min': 42}))
    assert ai_measured(partial) is None and ai_measured(complete) == 42
    assert ai_measured(SimpleNamespace(simulation_result=None)) is None


def test_live_feed_receives_every_agent_step_without_changing_the_run():
    from test_orchestrator import adapter, case, extraction, perfect_facts, review, specialist
    seen = []
    s = case('DEV-003')
    a = adapter([extraction(perfect_facts('DEV-003')), specialist(), specialist(), review()])
    result = AgentOrchestrator(a, on_message=seen.append).run(s, 'multi')
    working = [m for m in seen if m['recipient'] == 'working']
    assert [m['stage'] for m in working] == ['investigate', 'resources', 'priorities', 'schedule', 'review']
    assert len(seen) - len(working) == len(result.messages)

    def broken(_):
        raise RuntimeError('display failure')
    b = adapter([extraction(perfect_facts('DEV-003')), specialist(), specialist(), review()])
    assert AgentOrchestrator(b, on_message=broken).run(s, 'multi').status == 'awaiting_approval'

    class Status:
        def __init__(self):
            self.lines, self.labels = [], []
        def update(self, **kw):
            self.labels.append(kw.get('label'))
        def markdown(self, text):
            self.lines.append(text)
    status = Status()
    feed = LiveFeed(status)
    for m in seen:
        feed(m)
    assert any('Network Investigator** is reading the incident reports' in l for l in status.lines)
    assert feed.count == len(result.messages) and 'Plan Reviewer is working…' in status.labels


def test_planning_page_has_four_steps_and_opens_on_generate(app_root, monkeypatch):
    at = app(app_root, monkeypatch)
    at.radio(key='workspace_page').set_value('Planning').run()
    assert not at.exception
    assert [t.label for t in at.tabs][:4] == ['① Generate', '② Inspect plan', '③ Review & approve', '④ Simulate']
    assert at.button(key='generate_plan') and at.button(key='approve_plan') and at.button(key='simulate_plan')


def test_map_draws_planned_routes_per_crew():
    from test_day2_views import fake_multi_run
    result = fake_multi_run()
    rows = M.layer_rows(result.state.scenario, plan=result.plan)
    assert rows['routes'] and all(len(r['path']) >= 2 for r in rows['routes'])
    assert {r['crew_id'] for r in rows['routes']} <= {a.crew_id for a in result.plan.actions}
    assert M.layer_rows(result.state.scenario)['routes'] == []
