"""Dashboard foundation and incident inspection; rendering never invokes a model."""
from html import escape
from pathlib import Path

from dotenv import load_dotenv
import streamlit as st

from project.llm.health import preflight
from project.ui.catalog import load_catalog
from project.ui.backend import connect_static_backend
from project.ui.incident import render_incident
from project.ui.planning import render_planning
from project.ui.session import get_dashboard_session
from project.ui.review_service import active_approval
from project.ui.history import render_history
from project.ui.outcomes import render_results
from project.ui.workflow import render_workflow
from project.ui.map_page import render_field_page, render_map_page
from project.ui.benchmark_page import render_benchmark
from project.ui.baseline_compare import render_baseline_compare
from project.ui.plan_export import render_plan_export
from project.ui.notifications import badge_counts, notifications
from project.ui.upload_view import render_upload
from project.ui.whatif import has_truth
from project.ui.whatif_page import render_whatif
from project.ui.auth_view import current_user, render_identity, render_login, render_roles_panel

PAGES = ('Overview', 'Incident', 'Map', 'Planning', 'Field work', 'Results', 'What-if', 'Benchmark', 'History',
         'Settings')


def _pill(text, amber=False):
    return f'<span class="relink-pill{" amber" if amber else ""}">{escape(text)}</span>'


def _steps(connected=False):
    labels = (
        ('01', 'Understand the incident', 'Choose a validated scenario and establish the operating context.', 'Available'),
        ('02', 'Build a recovery plan', 'Inspect evidence and coordinate a feasible restoration schedule.', 'Available'),
        ('03', 'Review and approve', 'Keep the operator in control before any simulated action.', 'Available'),
        ('04', 'Measure the outcome', 'Compare independently simulated service restoration.', 'Available' if connected else 'Awaiting simulator'),
    )
    for column, (number, title, description, status) in zip(st.columns(4), labels):
        with column, st.container(border=True):
            st.html(f'<div class="relink-step"><div class="relink-step-no">STEP {number}</div>'
                    f'<div class="relink-step-title">{title}</div>'
                    f'<div class="relink-muted">{description}</div></div>'
                    + _pill(status, status != 'Available'))


def _overview(choice, session):
    scenario = choice.scenario
    st.html('<div class="relink-eyebrow">Incident workspace</div>')
    st.title('Restore with a clearer picture.')
    st.write('Bring the incident, field resources and recovery decisions into one workspace.')
    render_workflow(session, choice)
    st.html(_pill('Synthetic scenario') + _pill('Dashboard foundation', True))
    st.write('')
    for column, (label, value, help_text) in zip(st.columns(4), (
        ('Sites', len(scenario.sites), 'Fictional sites described by the selected visible input.'),
        ('Crews', len(scenario.crews), 'Inventory count; availability is checked during planning.'),
        ('Reports', len(scenario.reports), 'Visible report inventory; inspect extracted/resolved facts on Planning after a run.'),
        ('Horizon', f'{scenario.horizon_min / 60:g} h', 'Total scenario horizon, not time until a real-world deadline.'),
    )):
        column.metric(label, value, help=help_text)
    st.write('')
    left, right = st.columns([1.6, 1])
    with left, st.container(border=True):
        st.subheader('Your selected incident')
        st.markdown(f'**{scenario.scenario_id}**')
        st.write(scenario.region_label)
        st.caption(f'Incident clock: minute {scenario.current_time_min} of {scenario.horizon_min}')
        st.write(f'{len(scenario.links)} backhaul links · {len(scenario.roads)} road connections · '
                 f'{len(scenario.services)} service associations')
        st.caption('Synthetic network positions are not real tower locations or coverage estimates.')
    with right, st.container(border=True):
        st.subheader('Planning workspace')
        st.write('Open Planning to generate a schedule and inspect the recorded evidence and checks.')
        st.caption('Planning runs only when you explicitly click Generate plan on the Planning page.')
        st.caption('Review and approve on Planning, then simulate or continue the incident.' if session.core.simulator else
                   'Review and record your decision on Planning. Simulation awaits the independent evaluator.')
    st.write('')
    st.subheader('From incident to measured recovery')
    _steps(session.core.simulator is not None)


def _settings(health, session, choice, user=None, root=None):
    st.html('<div class="relink-eyebrow">Settings</div>')
    st.title('Know what is ready.')
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader('Hosted model')
        st.write(f'Provider: {health["provider"]}')
        st.write(f'Model: {health["model"] or "Not selected"}')
        st.write('Reasoning effort: ' + (health.get('reasoning_effort') or 'Provider default'))
        st.write('API credential: ' + ('Present' if health['key_present'] else 'Missing'))
        if health['status'] == 'blocked':
            st.warning('Hosted planning configuration is incomplete.')
            for reason in health['reasons']:
                st.write('• ' + reason)
        else:
            st.success('Configuration present; live connectivity remains unverified.')
        st.caption('No API request is made by this check. Set configuration locally and restart the app to apply changes.')
    with right, st.container(border=True):
        st.subheader('Workspace session')
        st.write('Session: ' + session.session_id[:8])
        st.write(f'Selection revision: {session.selection_revision}')
        st.write('Scenario: ' + (choice.scenario.scenario_id if choice else 'None'))
        status = 'Approved for simulation' if choice and active_approval(session, choice) else 'Rejected' if session.last_decision and session.last_decision.approval.decision == 'reject' else 'Not approved'
        st.write('Approval: ' + status)
    if user is not None:
        render_roles_panel(user, root)
        st.caption('Navigation reruns preserve this browser session. Reloading or reconnecting may start a new session. '
                   'Decisions are recorded under your signed-in identity (demo-grade local sign-in).')
    with st.expander('Data source and implementation status'):
        if choice:
            st.code(choice.key, language=None)
            st.write('Content hash: ' + choice.content_hash[:16])
        st.write('Available: incident inspection, planning, recorded decisions, approval-gated simulator boundary, read-only history, exports and evaluator-output views.')
        st.write('Simulator: ' + (session.simulator_label or 'Not installed/connected'))
        st.write('Pending: independent human benchmark audit and production identity (SSO/MFA).')


def render_app(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    load_dotenv(root / '.env', override=False)
    st.set_page_config(page_title='RE:L!NK · Recovery workspace', page_icon='📡', layout='wide',
                       initial_sidebar_state='expanded')
    st.html('<style>' + Path(__file__).with_name('styles.css').read_text() + '</style>')
    user = current_user()
    if user is None:
        render_login(root)
        return
    st.session_state['operator_label'] = user.label
    catalog = load_catalog(root)
    session = get_dashboard_session(st.session_state)
    health = preflight()
    choice = None

    with st.sidebar:
        st.html('<div class="relink-brand">RE:<span>L!NK</span></div>'
                '<div class="relink-muted">Restore connectivity.<br>Coordinate recovery.</div>'
                '<div class="relink-rule"></div>')
        st.caption('WORKSPACE')
        nav = st.container()
        st.divider()
        st.caption('ACTIVE SCENARIO')
        if catalog.choices:
            by_key = {item.key: item for item in catalog.choices}
            keys = list(by_key)
            pending = st.session_state.pop('pending_scenario', None)
            if pending in by_key:
                st.session_state['scenario_picker'] = pending
            # A data publication may remove the previously selected development fixture.
            if st.session_state.get('scenario_picker') not in by_key:
                st.session_state['scenario_picker'] = keys[catalog.default_index]
            key = st.selectbox('Scenario', keys, format_func=lambda key: by_key[key].label,
                               key='scenario_picker', label_visibility='collapsed')
            choice = by_key[key]
            changed = session.select(choice)
            connect_static_backend(session, choice, root)
            choice = session.continuation_choice or session.confirmation_choice or choice
            if changed and session.selection_revision > 1:
                st.caption('Scenario changed. Previous plan, approval and results were cleared.')
            st.caption('Operator clarification active · inspect resolved facts on Planning' if choice.source=='operator_confirmed' else
                       'Development fixture' if catalog.using_fixtures else 'Processed demo/development input')
        else:
            session.clear_selection()
            st.warning('No valid visible scenarios found.')
        render_upload(root, catalog, choice, user)
        todo = notifications(session, choice, user)
        counts = badge_counts(todo)
        with nav:
            page = st.radio('Workspace navigation', PAGES, key='workspace_page', label_visibility='collapsed',
                            format_func=lambda p: f'{p}  🔴 {counts[p]}' if counts.get(p) else p)
            if todo:
                st.html('<div class="relink-todo"><b>For you now</b>' +
                        ''.join(f'<div>• {escape(msg)} <span>({escape(where)})</span></div>' for where, msg in todo) +
                        '</div>')
        render_identity(user)
        st.divider()
        st.html(_pill('Synthetic workspace'))
        st.caption('Hosted model: ' + ('setup needed' if health['status'] == 'blocked' else 'configured, unverified'))
        st.caption('Browsing makes no model requests.')

    if catalog.using_fixtures:
        st.caption('DEVELOPMENT INPUT · Processed data is not available. Using validated synthetic test fixtures.')
    if catalog.issues:
        with st.expander(f'Input checks · {len(catalog.issues)} notice(s)'):
            for issue in catalog.issues:
                st.warning(issue)
    if page == 'Settings':
        _settings(health, session, choice, user, root)
    elif page == 'History':
        render_history(root, choice)
    elif page == 'Benchmark':
        render_benchmark(root)
    elif choice is None:
        st.title('Prepare your incident workspace.')
        st.error('No valid scenario can be selected.')
        st.write('Add approved visible inputs under data/processed/agent_inputs/demo or development. '
                 'The bundled tests/core/fixtures folder is the development fallback.')
    elif page == 'Overview':
        _overview(choice, session)
    elif page == 'Incident':
        render_incident(choice)
    elif page == 'Map':
        render_map_page(choice, session)
    elif page == 'Planning':
        render_planning(choice, session, root)
    elif page == 'Field work':
        render_field_page(choice, session, root)
    elif page == 'What-if':
        render_whatif(choice, session, root)
    else:
        render_results(session, choice)
        if choice is not None and choice.source != 'development_fixture' and has_truth(choice):
            render_baseline_compare(session, choice, root)
        render_plan_export(session, choice)
    st.html('<div class="relink-footer">HyperReAIlity · SLIIT &nbsp; / &nbsp; AI Catalyst 2026'
            ' &nbsp; / &nbsp; Synthetic decision-support workspace</div>')
