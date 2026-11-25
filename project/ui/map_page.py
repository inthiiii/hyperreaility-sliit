"""Map page and Field work page."""
import time

import streamlit as st

from project.auth import can
from project.ui.auth_view import current_user, needs_role
from project.ui.confirmation import render_confirmation
from project.ui.map_view import layer_rows, render_map
from project.ui.review_service import active_approval


def _current_plan(session, choice):
    result = session.core.current
    if result is None or result.state.source_hash != choice.content_hash:
        return None
    return result


def render_map_page(choice, session):
    scenario = choice.scenario
    st.html('<div class="relink-eyebrow">Incident map</div>')
    st.title('See where the network is hurting.')
    st.caption('Fictional sites placed in real Colombo, Gampaha and Kalutara towns. '
               'Not real tower locations, routes or coverage.')
    result = _current_plan(session, choice)
    sim = session.simulation_result
    replay = sim is not None and result is not None and sim.plan_id == (result.plan.plan_id if result.plan else None)
    left, right = st.columns([3, 1])
    with right:
        views = ['Evidence now'] + (['Simulated restoration'] if replay else [])
        view = st.radio('Show', views, key='map_view_mode')
        basemap = False  # Streamlit supplies its own basemap; district outlines draw on top.
        minute = None
        play = False
        show_routes = st.toggle('Show planned crew routes', key='map_routes', value=True,
                                disabled=result is None or result.plan is None)
        if view == 'Simulated restoration':
            minute = st.slider('Incident minute', scenario.current_time_min, scenario.horizon_min,
                               scenario.current_time_min, step=5, key='map_minute')
            play = st.button('▶ Play the restoration', key='map_play', width='stretch')
        st.markdown('**Legend**')
        if view == 'Simulated restoration':
            st.caption('🟢 service up · 🔴 service down · ⚪ no service · 🔵 crew (planned position)')
        else:
            st.caption('🟢 OK · 🔴 fault · 🟡 unknown · red dashed road = closed · ⚪ core / depot')
        st.caption('Larger circles carry a critical service.')
    with left:
        observations = result.state.resolved_observations if result is not None else None
        plan = result.plan if result is not None and show_routes else None
        trajectory = sim.trajectory if view == 'Simulated restoration' else None
        frame = st.empty()
        if play:
            # Simple replay: redraw every 30 incident minutes.
            for step in range(scenario.current_time_min, scenario.horizon_min + 1, 30):
                with frame.container():
                    st.caption(f'Incident minute {step} of {scenario.horizon_min}')
                    render_map(scenario, observations=observations, trajectory=trajectory, minute=step, plan=plan,
                               basemap=basemap)
                time.sleep(0.5)
        with frame.container():
            rows = render_map(scenario, observations=observations, trajectory=trajectory,
                              minute=minute if not play else scenario.horizon_min, plan=plan, basemap=basemap)
    if view == 'Evidence now':
        st.caption('Using the resolved evidence from the current plan.' if result is not None else
                   'Using the initial snapshot. Generate a plan to show what the agents resolved.')
    counts = {}
    for site in rows['sites']:
        counts[site['status']] = counts.get(site['status'], 0) + 1
    st.write(' · '.join(f'{k}: {v}' for k, v in sorted(counts.items())))
    if rows['crews']:
        st.dataframe([{'Crew': c['crew_id'], 'At minute ' + str(minute): c['doing']} for c in rows['crews']],
                     hide_index=True, width='stretch')
    with st.expander('Site directory'):
        st.dataframe([{'Site': s['site_id'], 'Name': s['name'], 'Code': s['code'], 'District': s['district'],
                       'Status': s['status'], 'Critical service': '✓' if s['critical'] else ''}
                      for s in rows['sites']], hide_index=True, width='stretch')


def render_field_page(choice, session, root):
    user = current_user()
    st.html('<div class="relink-eyebrow">Field work</div>')
    st.title('Your jobs and field updates.')
    result = _current_plan(session, choice)
    approved = result is not None and active_approval(session, choice)
    if not approved:
        st.info('No approved plan is active. Jobs appear here after a Restoration Manager approves a plan.')
    else:
        crews = [c.crew_id for c in choice.scenario.crews]
        crew = st.selectbox('Crew', crews, key='field_crew')
        names = {s.site_id: s.label for s in choice.scenario.sites}
        jobs = [a for a in result.plan.actions if a.crew_id == crew]
        if jobs:
            st.dataframe([{'Order': i + 1, 'Job': a.action_id, 'What': a.kind.replace('_', ' '),
                           'Where': f'{names.get(a.target_id, a.target_id)} ({a.target_id})',
                           'Leave at (min)': a.departure_min, 'Start work (min)': a.work_start_min,
                           'Finish (min)': a.work_end_min,
                           'Route': ' → '.join(names.get(p, p) for p in a.travel_route)}
                          for i, a in enumerate(jobs)], hide_index=True, width='stretch')
        else:
            st.caption('No jobs assigned to this crew in the approved plan.')
        st.caption('Planned instructions for the simulation only; nothing is dispatched to real crews.')
    st.subheader('Report what you found')
    st.write('A field update becomes confirmed evidence. It **cancels the current approval** and the plan must be '
             'regenerated and approved again.')
    if not can(user, 'confirm_fact'):
        st.caption(needs_role('confirm_fact'))
    render_confirmation(choice, session, root)
