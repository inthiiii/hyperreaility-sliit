"""What-if page: sliders for a lost crew and closed roads, then replan and compare."""
import altair as alt
import pandas as pd
import streamlit as st

from project.ui.whatif import compare, has_truth, load_truth


def _current(session, choice):
    result = session.core.current
    if result is None or result.plan is None or result.state.source_hash != choice.content_hash:
        return None
    return result


def render_whatif(choice, session, root):
    st.html('<div class="relink-eyebrow">What-if</div>')
    st.title('Stress-test the plan.')
    st.write('Take a crew away or close a road, then see whether the current plan still works and what a fresh '
             'plan would achieve.')
    st.caption('Sandbox only: your plan, approval and results never change. Replanning uses CP-SAT on the facts '
               'the agents already established, so no model is called and nothing is charged.')
    result = _current(session, choice)
    if result is None:
        st.info('Generate a plan first (Planning → ① Generate). The what-if starts from the current plan.')
        return
    scenario = result.state.scenario
    if scenario.current_time_min:
        st.info('What-if is available at the start of an incident (minute 0). This incident has already advanced.')
        return
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.markdown('**Crews**')
        crews_out = {}
        for crew in scenario.crews:
            until = st.slider(f'{crew.crew_id} unavailable until minute', 0, scenario.horizon_min, 0, step=30,
                              key=f'whatif_crew_{crew.crew_id}',
                              help=f'{crew.crew_id} skills: {", ".join(crew.skills)}. '
                                   f'{scenario.horizon_min} = out for the whole incident.')
            if until:
                crews_out[crew.crew_id] = until
    with right, st.container(border=True):
        st.markdown('**Roads**')
        names = {s.site_id: s.label for s in scenario.sites}
        names.update({scenario.depot_id: 'Depot', scenario.core_id: 'Core'})
        open_roads = [r for r in scenario.roads if result.state.resolved_observations.roads.get(r.road_id) is not False]
        closed = st.multiselect('Close these roads', [r.road_id for r in open_roads], key='whatif_roads',
                                format_func=lambda rid: next(f'{r.road_id}: {names.get(r.origin, r.origin)} ↔ '
                                                             f'{names.get(r.to, r.to)} ({r.travel_minutes} min)'
                                                             for r in scenario.roads if r.road_id == rid))
        used = sorted({rid for a in result.plan.actions for rid in _roads_on(scenario, a.travel_route)})
        st.caption('Roads the current plan uses: ' + (', '.join(used) or 'none'))
    run = st.button('Replan and compare', key='whatif_run', type='primary', disabled=not crews_out and not closed)
    key = (result.plan.plan_id, tuple(sorted(crews_out.items())), tuple(sorted(closed)))
    if run:
        with st.spinner('Replanning and measuring the three options…'):
            truth = load_truth(root, choice) if has_truth(choice) else None
            st.session_state['whatif_out'] = (key, compare(result, crews_out, closed, truth))
    stored = st.session_state.get('whatif_out')
    if not stored or stored[0] != key:
        if crews_out or closed:
            st.caption('Press Replan and compare to measure this disruption.')
        return
    _render(stored[1], has_truth(choice))


def _roads_on(scenario, route):
    pairs = {frozenset((a, b)) for a, b in zip(route, route[1:])}
    return [r.road_id for r in scenario.roads if frozenset((r.origin, r.to)) in pairs]


def _render(out, measured):
    rows = []
    for row in out['rows']:
        m = row.get('measured') or {}
        rows.append({'Option': row['Option'], 'Valid': '✓' if row['valid'] else '✗ would fail',
                     'Jobs': len(row['plan'].actions),
                     'Weighted downtime': m.get('weighted_downtime_min'),
                     'Critical downtime (min)': m.get('critical_service_downtime_min'),
                     'Services up at end': m.get('services_up_at_end')})
    st.subheader('Result')
    st.dataframe(rows, hide_index=True, width='stretch')
    current, kept, replanned = out['rows']
    if not kept['valid']:
        st.error('The current plan would not survive this disruption: ' + '; '.join(kept['problems'][:3]))
    else:
        st.success('The current plan still passes validation under this disruption.')
    if measured and all('weighted_downtime_min' in (r.get('measured') or {}) for r in (current, replanned)):
        base, new = current['measured']['weighted_downtime_min'], replanned['measured']['weighted_downtime_min']
        st.metric('Cost of the disruption after replanning', f'{new - base:+,.0f} weighted service-minutes',
                  delta=f'{(new - base) / base * 100 if base else 0:+.1f} %', delta_color='inverse')
        chart = pd.DataFrame([{'Option': r['Option'], 'Weighted downtime': r['Weighted downtime']} for r in rows
                              if r['Weighted downtime'] is not None])
        st.altair_chart(alt.Chart(chart).mark_bar(cornerRadius=3).encode(
            x=alt.X('Weighted downtime:Q', title='Weighted downtime (lower is better)'),
            y=alt.Y('Option:N', sort=None, title=None),
            color=alt.Color('Option:N', legend=None, scale=alt.Scale(
                domain=['Current plan · normal conditions', 'Current plan · with the disruption',
                        'Replanned for the disruption'], range=['#8D9EB3', '#ff9f5a', '#54D6BB']))
        ).properties(height=150), width='stretch')
    elif not measured:
        st.caption('Uploaded incidents have no simulator answer, so only validity and jobs are compared.')
    a, b = st.columns(2)
    a.markdown('**Jobs added by the replan**')
    a.write(', '.join(f'{c} {j}' for c, j in out['added']) or 'none')
    b.markdown('**Jobs dropped or moved**')
    b.write(', '.join(f'{c} {j}' for c, j in out['dropped']) or 'none')
    st.caption('Measured in separate what-if simulator episodes with the disruption applied to both the visible '
               'incident and the simulator. If a mid-incident event occurs, the remainder is replanned with CP-SAT.')
