"""Map page and Field work page."""
import time

import streamlit as st

from project.auth import can
from project.ui.auth_view import current_user, needs_role
from project.ui.confirmation import render_confirmation
from project.ui.map_view import (crew_color, evidence_changes, itineraries, render_map, replay_events,
                                 replay_kpis)
from project.ui.review_service import active_approval


def _current_plan(session, choice):
    result = session.core.current
    if result is None or result.state.source_hash != choice.content_hash:
        return None
    return result


CHAPTERS = ['① Reported damage', '② What the agents established', '③ The plan', '④ Restoration replay']
INTRO = {
    0: 'What the network operations centre knew **before** anyone read the reports: alarms that parse cleanly '
       'are known; everything else is amber (unknown).',
    1: 'What the agents established from the messy reports. Yellow rings mark sites whose status changed.',
    2: 'Where each crew goes and in what order. Colours match the crew list on the right.',
    3: 'The approved plan played out in the independent simulator. Sites turn green as service returns.',
}
SPEEDS = {'Slow': 0.9, 'Normal': 0.45, 'Fast': 0.15}


def _go(index):
    st.session_state['map_chapter'] = CHAPTERS[index]


def _locked(index, result, replay):
    if index in (1, 2) and (result is None or result.plan is None):
        return 'Generate a plan first: Planning → ① Generate.'
    if index == 3 and not replay:
        return 'Approve and simulate the plan first: Planning → ③ Review & approve, then ④ Simulate.'
    return None


def _counts(rows):
    counts = {}
    for site in rows['sites']:
        counts[site['status']] = counts.get(site['status'], 0) + 1
    return counts


def _kpi_html(k, minute, horizon):
    pct = 100 * (minute / horizon if horizon else 0)
    cells = [('Incident minute', f'{minute} / {horizon}'), ('Services up', f"{k['up']} / {k['total']}"),
             ('Critical up', f"{k['critical_up']} / {k['critical_total']}"),
             ('Weighted availability', f"{k['weighted_pct']:.0f} %")]
    body = ''.join(f'<div class="rl-kpi"><span>{a}</span><b>{b}</b></div>' for a, b in cells)
    return (f'<div class="rl-kpis">{body}</div><div class="rl-bar"><div style="width:{pct:.1f}%"></div></div>'
            '<style>.rl-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin:2px 0 6px}'
            '.rl-kpi{border:1px solid #22303F;border-radius:10px;padding:6px 10px;background:#0D141F}'
            '.rl-kpi span{display:block;font-size:11.5px;color:#8D9EB3}.rl-kpi b{font-size:18px;color:#EAF1F8}'
            '.rl-bar{height:6px;border-radius:3px;background:#182334;overflow:hidden;margin-bottom:6px}'
            '.rl-bar div{height:100%;background:#54D6BB;transition:width .3s}</style>')


def _event_html(events, limit=8):
    rows = ''.join(f'<div><span>min {t:>3}</span> {icon} {text}</div>' for t, icon, text in events[-limit:][::-1])
    return ('<div class="rl-events">' + (rows or '<div>Nothing has happened yet.</div>') + '</div>'
            '<style>.rl-events{border:1px solid #22303F;border-radius:10px;padding:8px 12px;background:#0D141F;'
            'font-size:13px;color:#B8C6D6;max-height:220px;overflow:auto}.rl-events div{padding:2px 0}'
            '.rl-events span{color:#8D9EB3;display:inline-block;width:62px;font-variant-numeric:tabular-nums}</style>')


def render_map_page(choice, session):
    scenario = choice.scenario
    st.html('<div class="relink-eyebrow">Incident map</div>')
    st.title('See where the network is hurting.')
    st.caption('Fictional sites placed in real Colombo, Gampaha and Kalutara towns. '
               'Not real tower locations, routes or coverage.')
    result = _current_plan(session, choice)
    sim = session.simulation_result
    replay = sim is not None and result is not None and sim.plan_id == (result.plan.plan_id if result.plan else None)
    if st.session_state.get('map_chapter') not in CHAPTERS:
        st.session_state['map_chapter'] = CHAPTERS[3 if replay else 2 if result is not None and result.plan else 0]
    chapter = st.radio('Map story', CHAPTERS, key='map_chapter', horizontal=True, label_visibility='collapsed')
    index = CHAPTERS.index(chapter)
    st.progress((index + 1) / len(CHAPTERS))
    lock = _locked(index, result, replay)
    if lock:
        st.info(lock + ' Showing ① Reported damage until then.')
        index = 0
    st.markdown(INTRO[index])
    observations = scenario.observed_state
    if index >= 1 and result is not None:
        observations = result.state.resolved_observations
    plan = result.plan if result is not None and index >= 2 else None
    changes = evidence_changes(scenario, result.state.resolved_observations) if result is not None else []

    left, right = st.columns([2.6, 1.2])
    with right:
        if index == 3:
            play_panel = st.container()
        elif index == 2:
            _itinerary_panel(scenario, plan)
        elif index == 1:
            st.markdown(f'**{len(changes)} change(s) from the reports**')
            if changes:
                st.dataframe([{'Where': c['Where'], 'What': c['What'], 'Change': f"{c['Before']} → {c['Now']}"}
                              for c in changes],
                             hide_index=True, width='stretch', height=min(360, 38 + 35 * len(changes)))
                st.caption('Sources for each fact: Planning → ② Inspect plan → Evidence.')
            else:
                st.caption('The agents confirmed the snapshot; nothing changed.')
        else:
            counts = {}
            for s in scenario.sites:
                o = observations.sites[s.site_id]
                state = 'fault' if False in (o.equipment_ok, o.grid_power_ok) else \
                    'unknown' if None in (o.equipment_ok, o.grid_power_ok) else 'OK'
                counts[state] = counts.get(state, 0) + 1
            for label in ('OK', 'fault', 'unknown'):
                st.metric(f'Sites {label}', counts.get(label, 0))
            closed = [r for r, v in observations.roads.items() if v is False]
            st.caption('Closed roads: ' + (', '.join(closed) or 'none known'))
        st.markdown('**Legend**')
        if index == 3:
            st.caption('🟢 service up · 🔴 service down · ⚪ no service · coloured dots = crews (planned position)')
        else:
            st.caption('🟢 OK · 🔴 fault · 🟡 unknown · red dashed road = closed · ⚪ core / depot. '
                       'Larger circles carry a critical service.')

    minute = None
    with left:
        if index == 3:
            with play_panel:
                minute = st.slider('Incident minute', scenario.current_time_min, scenario.horizon_min,
                                   scenario.current_time_min, step=5, key='map_minute')
                speed = st.select_slider('Replay speed', list(SPEEDS), value='Normal', key='map_speed')
                play = st.button('▶ Play the restoration', key='map_play', type='primary', width='stretch')
            intervals = sim.run_metadata.get('service_availability') or None
            frame = st.empty()
            steps = ([*range(scenario.current_time_min, scenario.horizon_min, 15), scenario.horizon_min]
                     if play else [minute])
            for i, step in enumerate(steps):
                with frame.container():
                    st.html(_kpi_html(replay_kpis(scenario, sim.trajectory, step, intervals), step, scenario.horizon_min))
                    rows = render_map(scenario, observations=observations, trajectory=sim.trajectory, minute=step,
                                      plan=plan, height=470, intervals=intervals)
                    st.markdown('**What happened**')
                    st.html(_event_html(replay_events(scenario, sim.trajectory, plan, step, intervals)))
                if i < len(steps) - 1:
                    time.sleep(SPEEDS[speed])
            minute = steps[-1]
        else:
            rows = render_map(scenario, observations=observations, plan=plan,
                              minute=scenario.current_time_min if plan is not None else None,
                              highlight=[c['site_id'] for c in changes if c['site_id']] if index == 1 else ())

    nav_back, nav_info, nav_next = st.columns([1, 2, 1])
    if index > 0:
        nav_back.button('← ' + CHAPTERS[index - 1], key='map_back', on_click=_go, args=(index - 1,), width='stretch')
    if index < 3:
        blocked = _locked(index + 1, result, replay)
        nav_next.button(CHAPTERS[index + 1] + ' →', key='map_next', on_click=_go, args=(index + 1,),
                        disabled=blocked is not None, help=blocked, width='stretch', type='primary')
    nav_info.caption(' · '.join(f'{k}: {v}' for k, v in sorted(_counts(rows).items())))
    if rows['crews'] and index == 3:
        st.dataframe([{'Crew': c['crew_id'], f'At minute {minute}': c['doing']} for c in rows['crews']],
                     hide_index=True, width='stretch')
    with st.expander('Site directory'):
        st.dataframe([{'Site': s['site_id'], 'Name': s['name'], 'Code': s['code'], 'District': s['district'],
                       'Status': s['status'], 'Critical service': '✓' if s['critical'] else ''}
                      for s in rows['sites']], hide_index=True, width='stretch')


def _itinerary_panel(scenario, plan):
    plans = itineraries(scenario, plan)
    if not plans:
        st.caption('This plan has no crew jobs.')
    for crew in sorted(c.crew_id for c in scenario.crews):
        r, g, b = crew_color(scenario, crew)
        st.html(f'<div style="display:flex;align-items:center;gap:8px;margin-top:6px"><span style="width:12px;'
                f'height:12px;border-radius:50%;background:rgb({r},{g},{b});display:inline-block"></span>'
                f'<b>Crew {crew}</b></div>')
        stops = plans.get(crew, [])
        if not stops:
            st.caption('No jobs.')
        for n, stop in enumerate(stops, 1):
            st.caption(f"{n}. **{stop['job']}** · {stop['what']} at {stop['where']} · leave {stop['leave']}, "
                       f"work {stop['start']}–{stop['end']}")


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
