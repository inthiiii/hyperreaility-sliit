"""Incident inspection views. All content comes from the visible ScenarioInput."""
import streamlit as st

from project.ui.incident_data import (
    action_rows, crew_rows, dependency_path, generator_rows, link_rows,
    local_site_status, observed_label, report_rows, road_rows, service_rows,
    site_rows, snapshot_counts,
)
from project.ui.topology import render_topology_svg

FILTER_KEYS = ('incident_site', 'incident_roads', 'incident_sources', 'incident_query',
               'incident_report', 'incident_critical_only')


def _table(rows, empty, key):
    if rows:
        st.dataframe(rows, hide_index=True, width='stretch', key=key)
    else:
        st.info(empty)


def _reset_filters(content_hash):
    if st.session_state.get('incident_input_hash') != content_hash:
        for key in FILTER_KEYS:
            st.session_state.pop(key, None)
        st.session_state['incident_input_hash'] = content_hash


def _network(scenario):
    left, right = st.columns([2.2, 1])
    with left:
        st.subheader('Backhaul dependencies')
        st.caption('Parent → child arrows show upstream dependencies. Roads are a separate undirected layer.')
        selection, layers = st.columns([1.5, 1])
        with selection:
            options = ['All sites', *[site.site_id for site in scenario.sites]]
            selected = st.selectbox('Inspect a site', options, key='incident_site')
        with layers:
            roads = st.checkbox('Show access roads', key='incident_roads')
        st.image(render_topology_svg(scenario, None if selected == 'All sites' else selected, roads),
                 width='stretch', caption='Synthetic dependency schematic · observed snapshot',
                 alt='Synthetic network dependency diagram. Arrows point upstream parent to downstream site; unknowns remain unknown. Equivalent site, link and road tables follow.')
        st.caption('Green / ✓: local observations OK · Coral / !: local fault · Amber / ?: unknown · '
                   'Gold outer ring: hosts a critical service. Core and depot are reference nodes.')
        st.caption('Schematic layout, not a geographic map. Diagram distances are not travel times. '
                   'Local observations OK does not establish end-to-end connectivity or restoration.')
    with right, st.container(border=True):
        if selected == 'All sites':
            st.subheader('Snapshot, not a verdict')
            st.write('Choose a site to inspect its equipment, power and dependency chain.')
            st.write('Unknown observations remain unknown. Reports are available in Evidence and have not been reconciled here.')
            st.caption('No agent has run. No repair, generator deployment or restoration is implied by this view.')
        else:
            site = next(site for site in scenario.sites if site.site_id == selected)
            observation = scenario.observed_state.sites[selected]
            st.subheader(selected)
            st.text(site.label)
            status = local_site_status(scenario, selected)
            if status == 'Local fault':
                st.error(status)
            elif status == 'Unknown':
                st.warning('Local observations include an unknown')
            else:
                st.info('Local observations OK; connectivity not evaluated')
            st.write('Equipment: ' + observed_label(observation.equipment_ok))
            st.write('Grid power: ' + observed_label(observation.grid_power_ok, 'Available', 'Unavailable'))
            st.caption('Upstream dependency chain')
            st.text(' → '.join(dependency_path(scenario, selected)))
            st.caption('Associated services')
            associated = [service for service in scenario.services if service.site_id == selected]
            if not associated:
                st.write('None recorded')
            for service in associated:
                st.text(f'{service.service_id} · {"Critical" if service.critical else "Standard"} · weight {service.weight}')
    with st.expander(f'Site observations · {len(scenario.sites)}'):
        _table(site_rows(scenario), 'No sites recorded.', 'site_observations')
    with st.expander(f'Backhaul observations · {len(scenario.links)}'):
        _table(link_rows(scenario), 'No links recorded.', 'link_observations')
    with st.expander(f'Access roads · {len(scenario.roads)}'):
        _table(road_rows(scenario), 'No access roads recorded.', 'road_observations')


def _evidence(scenario):
    st.subheader('Reports and provenance')
    st.caption('Times are incident minutes. Age is time since observation; no freshness threshold is inferred.')
    if not scenario.reports:
        st.info('No visible incident reports are recorded.')
        return
    source, search = st.columns([1, 1.4])
    with source:
        available = sorted({report.source_type for report in scenario.reports})
        sources = st.multiselect('Report sources', available, default=available, key='incident_sources')
    with search:
        query = st.text_input('Search reports', key='incident_query', placeholder='Report ID or report text')
    rows = report_rows(scenario, sources, query)
    st.caption(f'Showing {len(rows)} of {len(scenario.reports)} visible reports')
    _table(rows, 'No reports match these filters. Adjust the search or selected sources.', 'incident_reports')
    st.info('A recognized source type does not verify the report content or resolve a conflict. '
            'Extraction, reconciliation and confirmation arrive with the planning workflow.')
    if rows:
        ids = [row['Report'] for row in rows]
        if st.session_state.get('incident_report') not in ids:
            st.session_state['incident_report'] = ids[0]
        report_id = st.selectbox('Inspect a report', ids, key='incident_report')
        report = next(report for report in scenario.reports if report.report_id == report_id)
        with st.container(border=True):
            st.caption(f'{report.report_id} · {report.source_type} · observed {report.observed_at_min} min · received {report.received_at_min} min')
            st.text(report.text)


def _resources(scenario):
    st.subheader('Field resources')
    st.caption('Inventory and recorded time windows only. This view does not assign a crew or certify a route.')
    st.markdown('**Crews**')
    _table(crew_rows(scenario), 'No crews are recorded. Planning must expose unmet resource needs.', 'incident_crews')
    st.caption('A crew is in its recorded window when start ≤ current minute < end; this does not establish that it is idle or reachable.')
    st.markdown('**Generators**')
    _table(generator_rows(scenario), 'No generators are recorded.', 'incident_generators')
    st.caption('Autonomy begins after deployment completes. Availability does not imply allocation or current site power.')
    with st.expander(f'Permitted action catalogue · {len(scenario.action_options)}'):
        _table(action_rows(scenario), 'No actions are in the visible catalogue.', 'incident_actions')
        st.caption('Catalogue options are not a recommended schedule. Work duration excludes travel.')


def _priorities(scenario):
    st.subheader('Service priorities')
    policy = scenario.policy
    if policy.approved_for_simulation:
        st.success('Recorded policy is approved for simulation.')
    else:
        st.warning('Recorded policy is not approved for simulation; no plan can be approved under it.')
    st.caption(f'Policy evidence: {policy.evidence_id} · Standard weight {policy.standard_weight} · Critical weight {policy.critical_weight}')
    critical_only = st.checkbox('Critical services only', key='incident_critical_only')
    rows = service_rows(scenario, critical_only)
    _table(rows, 'No services match this view.', 'incident_services')
    st.caption('Weights are fixed by the supplied policy, not generated or edited here. '
               'Service associations are fictional; counts are not subscriber counts or measured service availability.')
    with st.expander('Recorded evidence and resource rules'):
        st.markdown('**Evidence rule**');st.text(policy.evidence_rule)
        st.markdown('**Crew-loss rule**');st.text(policy.on_crew_loss)
        st.write(f'Maximum generator deployments per scenario: {policy.max_generator_deployments_per_scenario}')


def render_incident(choice):
    scenario = choice.scenario
    _reset_filters(choice.content_hash)
    st.html('<div class="relink-eyebrow">Incident inspection</div>')
    st.title('Trace the fault. See the constraints.')
    st.text(f'{scenario.scenario_id} · {scenario.region_label}')
    st.caption(f'Observed snapshot · incident minute {scenario.current_time_min} of {scenario.horizon_min} · synthetic scenario')
    counts = snapshot_counts(scenario)
    for column, label, key in zip(st.columns(4),
        ('Site flags', 'Unknowns', 'Link faults', 'Critical services'),
        ('site_flags', 'unknowns', 'link_faults', 'critical_services')):
        column.metric(label, counts[key])
    st.caption('Counts describe the supplied snapshot only. Report text may contain additional or contradictory evidence; '
               'it is not automatically applied to the diagram.')
    network, evidence, resources, priorities = st.tabs(['Network', 'Evidence', 'Resources', 'Service priorities'])
    with network:
        _network(scenario)
    with evidence:
        _evidence(scenario)
    with resources:
        _resources(scenario)
    with priorities:
        _priorities(scenario)
