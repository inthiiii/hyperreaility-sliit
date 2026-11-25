"""What-if: the same incident planned without AI (CP-SAT on what software alone can read).

Runs only after the approved plan has been simulated over the whole incident.
The comparison uses a fresh, separate simulator episode with an automated
what-if approval; it never touches the session's plan, approval or results.
"""
from pathlib import Path

import streamlit as st

from project.auth import can, require
from project.core.coordinator import approve
from project.core.orchestrator import AgentOrchestrator
from project.data.evaluator import EvaluatorLoader
from project.data.loader import CaseLoader
from project.simulation.episode import IncidentEpisode
from project.ui.auth_view import current_user, needs_role

WHAT_IF_OPERATOR = 'What-if comparison (automated, not an operational approval)'


def data_root_for(root, key):
    return (Path(root) / key).parents[3]


def ai_measured(session):
    result = session.simulation_result
    if result is None or result.run_metadata.get('measurement_scope') != 'complete_incident':
        return None
    return result.metrics.get('weighted_downtime_min')


def simulate_no_ai(root, key, planner='cp_sat', max_episodes=10):
    root = Path(root).resolve()
    data_root = data_root_for(root, key)
    case = CaseLoader(data_root / 'processed' / 'agent_inputs').load_case(Path(root) / key)
    truth = EvaluatorLoader(data_root / 'evaluation' / 'ground_truth').load(case.scenario_id)
    episode, scenario, version, actions = IncidentEpisode(case, truth), case, 1, 0
    for _ in range(max_episodes):
        run = AgentOrchestrator(planner=planner).run(scenario, 'template', state_version=version)
        if run.status != 'awaiting_approval':
            raise ValueError('No-AI baseline did not produce a valid plan')
        approval = approve(run.plan.plan_id, run.state.state_version, 'approve', plan=run.plan, state=run.state,
                           operator_id=WHAT_IF_OPERATOR)
        sim = episode.advance(scenario, run.plan, approval, state=run.state)
        actions += len(run.plan.actions)
        if episode.complete:
            return {'weighted_downtime_min': sim.metrics['weighted_downtime_min'],
                    'critical_service_downtime_min': sim.metrics.get('critical_service_downtime_min'),
                    'actions': actions, 'unresolved_facts': len(run.state.unresolved_facts), 'planner': planner}
        scenario, version = episode.checkpoint(), run.state.state_version + 1
    raise ValueError('Incident did not complete within the episode limit')


def render_baseline_compare(session, choice, root):
    st.subheader('What would have happened without AI?')
    st.caption('Plans the same incident with CP-SAT only. Without agents, software can use only what it can parse '
               'from the reports. The result is measured by the same independent simulator in a separate what-if run; '
               'your plan, approval and results are not changed.')
    measured = ai_measured(session)
    if measured is None:
        st.info('Available after the approved plan has been simulated to the end of the incident (all 720 minutes).')
        return
    user = current_user()
    allowed = can(user, 'view_history')
    cache = st.session_state.setdefault('no_ai_compare', {})
    key = (choice.key, session.core.approval.plan_hash if session.core.approval else None)
    if st.button('Compare with the no-AI baseline', key='compare_no_ai', disabled=not allowed,
                 help=None if allowed else needs_role('view_history')):
        try:
            require(user, 'view_history')
            cache[key] = simulate_no_ai(root, choice.key)
        except Exception as error:  # noqa: BLE001 - shown to the operator
            cache[key] = {'error': f'{type(error).__name__}: {error}'[:200]}
    outcome = cache.get(key)
    if not outcome:
        return
    if 'error' in outcome:
        st.error('Comparison could not run: ' + outcome['error'])
        return
    baseline = outcome['weighted_downtime_min']
    saved = baseline - measured
    left, middle, right = st.columns(3)
    left.metric('With RE:L!NK (approved plan)', f'{measured:,.0f}', help='Measured weighted downtime, service-minutes')
    middle.metric('CP-SAT without AI', f'{baseline:,.0f}')
    right.metric('Difference', f'{saved:,.0f}', delta=f'{(saved / baseline * 100) if baseline else 0:.1f} % less downtime'
                 if saved > 0 else None)
    st.caption(f"No-AI plan: {outcome['actions']} actions; it could not establish {outcome['unresolved_facts']} facts that "
               'were only stated in free-text reports. One incident only; see the Benchmark page for results across all '
               'held-out cases. If operator clarifications were recorded during your run, the AI side had that extra '
               'confirmed evidence.')
