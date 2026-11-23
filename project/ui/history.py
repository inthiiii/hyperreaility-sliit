"""Local read-only history and safe exports. Never restore active approvals."""
import streamlit as st
from project.core.coordinator import RunResult
from project.ui.history_data import (
    csv_export, filter_history, json_export, linked_simulation, load_history, public_payload, summary_rows,
)
from project.ui.outcomes import render_outcome
from project.ui.planning import _activity, _details, _evidence, _schedule


def render_history(root, choice=None):
    st.html('<div class="relink-eyebrow">History</div>')
    st.title('Every decision has a trail.')
    st.write('Inspect saved plans, operator decisions and attempts without rerunning the workflow.')
    st.caption('Read-only local records. Opening or downloading a record never activates a plan, '
               'restores an approval, invokes a model or starts simulation. Checksums are not signatures.')
    catalog = load_history(root)
    if catalog.issues:
        with st.expander(f'Record checks · {len(catalog.issues)} notice(s)'):
            for issue in catalog.issues:st.warning(issue)
    if not catalog.entries:
        st.info('No readable saved records yet. Generate a plan on Planning to create the first run record.')
        return
    kind_column, scenario_column, query_column = st.columns([1, 1, 1.5])
    with kind_column:
        kind = st.selectbox('Record type', ['All', 'run', 'decision', 'simulation', 'attempt'], key='history_kind')
    with scenario_column:
        scenarios = ['All', *sorted({item.scenario_id for item in catalog.entries})]
        if st.session_state.get('history_scenario') not in scenarios:
            st.session_state['history_scenario'] = choice.scenario.scenario_id if choice and choice.scenario.scenario_id in scenarios else 'All'
        scenario = st.selectbox('History incident', scenarios, key='history_scenario')
    with query_column:
        query = st.text_input('Search record IDs or status', key='history_query')
    entries = filter_history(catalog, kind, scenario, query)
    st.caption(f'{len(entries)} matching records · bounded local history window · historical coordinator statuses are not current operator authorization')
    if not entries:
        st.info('No records match these filters.');return
    rows = summary_rows(entries)
    st.dataframe(rows, hide_index=True, width='stretch')
    st.caption('Token totals are blank when provider reporting is incomplete; they are not a charge calculation. '
               'UI attempt metadata predates checksummed audits and is labelled unchecksummed.')
    st.download_button('Download filtered history CSV', csv_export(rows), file_name='relink-history.csv',
                       mime='text/csv', key='history_csv', on_click='ignore')
    by_key = {entry.key: entry for entry in entries}
    if st.session_state.get('history_record') not in by_key:
        st.session_state['history_record'] = entries[0].key
    selected = st.selectbox('Inspect saved record', list(by_key),
        format_func=lambda key: f'{by_key[key].kind} · {by_key[key].scenario_id} · {by_key[key].record_id[:12]} · {by_key[key].status}',
        key='history_record')
    entry = by_key[selected]
    st.caption(entry.relative_path + ' · ' + entry.integrity)
    st.download_button('Download selected record JSON', json_export(entry.payload),
        file_name=f'relink-{entry.kind}-{entry.record_id}.json', mime='application/json', key='history_json', on_click='ignore')
    if entry.kind == 'run':
        st.info('Historical plan inspection only. To create an active plan, use an explicit new request on Planning.')
        result = RunResult.model_validate(public_payload(entry.payload))
        schedule, evidence, activity, details = st.tabs(['Saved schedule', 'Saved evidence', 'Saved activity', 'Saved run details'])
        with schedule:_schedule(result)
        with evidence:_evidence(result)
        with activity:_activity(result)
        with details:_details(result, None)
    elif entry.kind == 'simulation':
        simulation, issue = linked_simulation(entry, catalog)
        if issue:st.info(issue)
        if simulation is not None:
            render_outcome(simulation, 'history_' + entry.record_id, historical=True)
    with st.expander('Saved record data · read only'):
        st.json(public_payload(entry.payload))
    st.caption('Exports remove recognized hidden-truth/future-event keys and credential patterns. '
               'This is not a general personal-data anonymizer; use only authorized, appropriately redacted records.')
