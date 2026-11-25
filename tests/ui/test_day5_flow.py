"""Live agent-flow diagram and the guided map story."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'core'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from project.core.coordinator import approve
from project.core.orchestrator import AgentOrchestrator
from project.data.evaluator import EvaluatorLoader
from project.simulation.episode import IncidentEpisode
from project.ui import map_view as M
from project.ui.agent_flow import FlowState, LiveFlow, events_from_messages, final_state

ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / 'releases/evidence-v3-20261126/data'


def test_live_flow_and_replay_end_in_the_same_state():
    from test_orchestrator import adapter, case, extraction, perfect_facts, review, specialist
    seen, s = [], case('DEV-003')
    result = AgentOrchestrator(adapter([extraction(perfect_facts('DEV-003')), specialist(), specialist(), review()]),
                               on_message=seen.append).run(s, 'multi')
    live = FlowState('multi', len(s.reports))
    for m in seen:
        live.apply(m)
    live.finish(result)
    replayed = final_state(result)
    assert live.status == replayed.status and live.notes == replayed.notes and live.used == replayed.used
    assert set(live.status.values()) == {'done'} and live.notes['operator'] == 'plan ready to approve'
    assert [e['stage'] for e in events_from_messages(result.messages) if e['recipient'] == 'working'] == \
        [m['stage'] for m in seen if m['recipient'] == 'working']


def test_flow_shows_the_reviewer_challenge_going_back():
    from test_day2_views import fake_multi_run
    state = final_state(fake_multi_run())
    assert state.challenges == 1 and ('reviewer', 'investigator') in state.used
    assert 'fact challenges go back (1)' in state.svg()
    assert state.status['operator'] == 'done'


def test_working_node_pulses_then_stops_if_the_run_escalates():
    state = FlowState('multi', 3, clock=lambda: 0.0)
    state.apply({'sender': 'network_investigator', 'recipient': 'working', 'stage': 'investigate', 'finding': None})
    assert state.status['investigator'] == 'working' and 'rl-pulse' in state.svg()
    assert state.now == 'Network Investigator is reading the incident reports…'
    state.finish(SimpleNamespace(status='escalated'))
    assert state.status['investigator'] == 'failed' and state.status['operator'] == 'failed'


def test_live_flow_redraws_and_escapes_text():
    drawn = []
    slot = SimpleNamespace(html=drawn.append)
    flow = LiveFlow(slot, 'single', 2)
    flow({'sender': 'single_agent', 'recipient': 'working', 'stage': 'analyse', 'finding': None})
    flow({'sender': 'single_agent', 'recipient': 'coordinator',
          'finding': {'stage': 'analyse', 'facts': [], 'ignored_reports': [{'report_id': '<b>x', 'kind': 'noise'}]}})
    assert len(drawn) == 3 and flow.count == 1 and '<b>x' not in drawn[-1]


def test_template_runs_get_a_flow_too():
    from test_orchestrator import case
    result = AgentOrchestrator().run(case('DEV-003'), 'template')
    state = final_state(result)
    assert state.status['parser'] == 'done' and state.status['scheduler'] == 'done'


def _simulated(cid='DEV-001'):
    from test_orchestrator import case
    s = case(cid)
    run = AgentOrchestrator().run(s, 'template')
    approval = approve(run.plan.plan_id, run.state.state_version, 'approve', plan=run.plan, state=run.state,
                       operator_id='test')
    truth = EvaluatorLoader(V3 / 'evaluation' / 'ground_truth').load(cid)
    sim = IncidentEpisode(s, truth).advance(s, run.plan, approval, state=run.state)
    return s, run, sim


def test_map_story_helpers():
    s, run, sim = _simulated()
    changes = M.evidence_changes(s, run.state.resolved_observations)
    assert all(c['Before'] != c['Now'] for c in changes)
    stops = M.itineraries(s, run.plan)
    assert sum(len(v) for v in stops.values()) == len(run.plan.actions)
    start = M.replay_kpis(s, sim.trajectory, s.current_time_min)
    end = M.replay_kpis(s, sim.trajectory, s.horizon_min)
    assert end['total'] == len(s.services) and end['up'] >= start['up']
    events = M.replay_events(s, sim.trajectory, run.plan, s.horizon_min)
    assert [t for t, *_ in events] == sorted(t for t, *_ in events)
    assert any(icon == '✅' for _, icon, _ in events) == bool(run.plan.actions)
    assert M.replay_events(s, sim.trajectory, run.plan, -1) == []
    rows = M.layer_rows(s, plan=run.plan, minute=s.current_time_min)
    assert all(c['color'] == M.crew_color(s, c['crew_id']) for c in rows['crews'])


def test_replay_uses_measured_intervals_from_the_incident_start():
    s, run, sim = _simulated('DEV-001')
    intervals = sim.run_metadata['service_availability']
    up_from_start = {sid for sid, d in intervals.items() if any(a <= s.current_time_min < b for a, b in d['intervals'])}
    start = M.replay_kpis(s, sim.trajectory, s.current_time_min, intervals)
    assert start['up'] == len(up_from_start)
    end = M.replay_kpis(s, sim.trajectory, s.horizon_min, intervals)
    final = set(next(e for e in reversed(sim.trajectory) if e['type'] == 'availability')['available_services'])
    assert end['up'] == len(final)
    rows = M.layer_rows(s, trajectory=sim.trajectory, minute=s.current_time_min, intervals=intervals)
    assert sum(r['status'] == 'Up' for r in rows['sites']) >= (1 if up_from_start else 0)
