"""Dashboard foundation and incident inspection; rendering never invokes a model."""
from html import escape
from pathlib import Path

from dotenv import load_dotenv
import streamlit as st

from project.llm.health import preflight
from project.ui.catalog import load_catalog
from project.ui.incident import render_incident
from project.ui.planning import render_planning
from project.ui.session import get_dashboard_session

PAGES = ('Overview', 'Incident', 'Planning', 'Results', 'Settings')


def _pill(text, amber=False):
    return f'<span class="relink-pill{" amber" if amber else ""}">{escape(text)}</span>'


def _steps():
    labels = (
        ('01', 'Understand the incident', 'Choose a validated scenario and establish the operating context.', 'Available'),
        ('02', 'Build a recovery plan', 'Inspect evidence and coordinate a feasible restoration schedule.', 'Available'),
        ('03', 'Review and approve', 'Keep the operator in control before any simulated action.', 'Pending integration'),
        ('04', 'Measure the outcome', 'Compare independently simulated service restoration.', 'Awaiting simulator'),
    )
    for column, (number, title, description, status) in zip(st.columns(4), labels):
        with column, st.container(border=True):
            st.html(f'<div class="relink-step"><div class="relink-step-no">STEP {number}</div>'
                    f'<div class="relink-step-title">{title}</div>'
                    f'<div class="relink-muted">{description}</div></div>'
                    + _pill(status, status != 'Available'))


def _overview(choice):
    scenario = choice.scenario
    st.html('<div class="relink-eyebrow">Incident workspace</div>')
    st.title('Restore with a clearer picture.')
    st.write('Bring the incident, field resources and recovery decisions into one workspace.')
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
        st.caption('Operator approval and independent simulation are pending integration.')
    st.write('')
    st.subheader('From incident to measured recovery')
    _steps()


def _results():
    st.html('<div class="relink-eyebrow">Results</div>')
    st.title('Evidence of recovery.')
    st.write('Measured outcomes will come from the independent simulator.')
    with st.container(border=True):
        st.subheader('No simulation results yet')
        st.write('Service restoration, downtime and critical-service interruption appear here after an approved simulation.')
        st.caption('Independent simulation is pending integration. Planner predictions will remain separately labelled.')


def _settings(health, session, choice):
    st.html('<div class="relink-eyebrow">Settings</div>')
    st.title('Know what is ready.')
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader('Hosted model')
        st.write(f'Provider: {health["provider"]}')
        st.write(f'Model: {health["model"] or "Not selected"}')
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
        st.write('Approval: none — controls pending integration')
        st.caption('Navigation reruns preserve this browser session. Reloading or reconnecting may start a new session. '
                   'An operator label does not authenticate a user.')
    with st.expander('Data source and implementation status'):
        if choice:
            st.code(choice.key, language=None)
            st.write('Content hash: ' + choice.content_hash[:16])
        st.write('Available: incident inspection, explicit planning, schedules, evidence, validation, run records and configuration inspection.')
        st.write('Pending: operator approval UI, authenticated identity, simulator and measured outcomes.')


def render_app(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    load_dotenv(root / '.env', override=False)
    st.set_page_config(page_title='RE:L!NK · Recovery workspace', page_icon='📡', layout='wide',
                       initial_sidebar_state='expanded')
    st.html('<style>' + Path(__file__).with_name('styles.css').read_text() + '</style>')
    catalog = load_catalog(root)
    session = get_dashboard_session(st.session_state)
    health = preflight()
    choice = None

    with st.sidebar:
        st.html('<div class="relink-brand">RE:<span>L!NK</span></div>'
                '<div class="relink-muted">Restore connectivity.<br>Coordinate recovery.</div>'
                '<div class="relink-rule"></div>')
        st.caption('WORKSPACE')
        page = st.radio('Workspace navigation', PAGES, key='workspace_page', label_visibility='collapsed')
        st.divider()
        st.caption('ACTIVE SCENARIO')
        if catalog.choices:
            by_key = {item.key: item for item in catalog.choices}
            keys = list(by_key)
            # A data publication may remove the previously selected development fixture.
            if st.session_state.get('scenario_picker') not in by_key:
                st.session_state['scenario_picker'] = keys[catalog.default_index]
            key = st.selectbox('Scenario', keys, format_func=lambda key: by_key[key].label,
                               key='scenario_picker', label_visibility='collapsed')
            choice = by_key[key]
            changed = session.select(choice)
            if changed and session.selection_revision > 1:
                st.caption('Scenario changed. Previous plan, approval and results were cleared.')
            st.caption('Development fixture' if catalog.using_fixtures else 'Processed demo/development input')
        else:
            session.clear_selection()
            st.warning('No valid visible scenarios found.')
        st.text_input('Operator label', key='operator_label', placeholder='Your name',
                      help='A session label only. This does not authenticate you or approve a plan.')
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
        _settings(health, session, choice)
    elif choice is None:
        st.title('Prepare your incident workspace.')
        st.error('No valid scenario can be selected.')
        st.write('Add approved visible inputs under data/processed/agent_inputs/demo or development. '
                 'The bundled tests/core/fixtures folder is the development fallback.')
    elif page == 'Overview':
        _overview(choice)
    elif page == 'Incident':
        render_incident(choice)
    elif page == 'Planning':
        render_planning(choice, session, root)
    else:
        _results()
    st.html('<div class="relink-footer">HyperReAIlity · SLIIT &nbsp; / &nbsp; AI Catalyst 2026'
            ' &nbsp; / &nbsp; Synthetic decision-support workspace</div>')
