"""Evaluator-reported results; no generated outcomes, predictions or baselines."""
import altair as alt
import pandas as pd
import streamlit as st

from project.ui.history_data import csv_export, json_export, public_payload
from project.ui.outcome_data import current_outcome, metric_rows, numeric_fields, plot_rows, trajectory_rows, service_interval_rows


def render_outcome(result, prefix, historical=False):
    test_output = bool(result.run_metadata.get('test_only') or result.run_metadata.get('injected_test'))
    if test_output:
        st.warning('TEST OUTPUT · injected/test callback data, not measured restoration evidence.')
    st.success('Evaluator result recorded' + (' in this historical record.' if historical else ' for the current plan.'))
    st.text(f'{result.scenario_id} · Plan {result.plan_id} · State {result.state_version}')
    st.caption('Evaluator-reported outputs are shown as returned. Interface checks do not validate the physical model or metric accuracy. '
               'No baseline improvement or financial saving is inferred.')
    metrics = metric_rows(result)
    st.subheader('Reported metrics')
    if metrics:
        display = [{**row, 'Value': 'Unavailable' if row['Value'] is None else str(row['Value'])} for row in metrics]
        st.dataframe(public_payload(display), hide_index=True, width='stretch')
        st.download_button('Download metrics CSV', csv_export(metrics), file_name='relink-metrics.csv',
                           mime='text/csv', key=prefix + '_metrics_csv', on_click='ignore')
    else:
        st.info('No metrics were returned. Missing values are not assumed to be zero.')
    intervals = service_interval_rows(result)
    if intervals:
        st.subheader('Measured service availability')
        st.caption('Bars show the evaluator’s half-open availability intervals [start, end), in incident minutes.')
        st.dataframe(intervals, hide_index=True, width='stretch')
        chart = alt.Chart(pd.DataFrame(intervals)).mark_bar().encode(
            x=alt.X('Start (min):Q', title='Incident minutes'), x2='End (min):Q',
            y=alt.Y('Service:N'), color='Critical:N',
            tooltip=['Service:N', 'Start (min):Q', 'End (min):Q', 'Available minutes:Q'])
        st.altair_chart(chart, width='stretch')
    if result.run_metadata.get('replan_required'):
        st.warning('Replanning required. This output does not authorize another plan or establish a completed replan/resume cycle.')
    action_outcomes = result.run_metadata.get('action_outcomes')
    if isinstance(action_outcomes, dict) and action_outcomes:
        st.subheader('Action outcomes')
        st.dataframe(public_payload([{'Action': key, **value} for key, value in action_outcomes.items()
                                    if isinstance(value, dict)]), hide_index=True, width='stretch')
    st.subheader('Restoration trajectory')
    rows = trajectory_rows(result)
    if not rows:
        st.info('No trajectory was returned by the evaluator.')
    else:
        st.dataframe(rows, hide_index=True, width='stretch')
        fields = numeric_fields(rows)
        config = result.run_metadata.get('trajectory_plot', {})
        if not isinstance(config, dict):config = {}
        declared_time = config.get('time_field')
        time_options = ['Choose a field', *fields]
        time_key = prefix + '_time'
        if st.session_state.get(time_key) not in time_options:
            st.session_state[time_key] = declared_time if declared_time in fields else time_options[0]
        time_field = st.selectbox('Trajectory time field', time_options, key=time_key)
        choices = [key for key in fields if key != time_field]
        declared_series = config.get('series', [])
        defaults = [key for key in declared_series if key in choices] if isinstance(declared_series, list) else []
        series_key = prefix + '_series'
        if series_key in st.session_state and any(key not in choices for key in st.session_state[series_key]):
            del st.session_state[series_key]
        series = st.multiselect('Trajectory numeric series', choices, default=defaults, key=series_key)
        st.caption('Field names are evaluator-defined. Choose the documented time/series fields; units and meaning are not guessed. '
                   'Optional trajectory_plot metadata can supply defaults.')
        if time_field != 'Choose a field' and series:
            try:
                data = pd.DataFrame(plot_rows(rows, time_field, series))
                time_unit = config.get('time_unit') if time_field == declared_time else None
                title = str(time_field) + (f' ({time_unit})' if time_unit else ' · unit not specified')
                # Keep unknown values as gaps; do not bridge them with a fabricated value.
                chart = alt.Chart(data).mark_line(point=True, invalid='break-paths-show-path-domains').encode(
                    x=alt.X('Time:Q', title=title), y=alt.Y('Value:Q', title='Reported value'),
                    color='Series:N', tooltip=['Time:Q', 'Series:N', 'Value:Q']).properties(height=280)
                st.altair_chart(chart, width='stretch')
            except ValueError as error:
                st.warning(str(error))
        st.download_button('Download trajectory CSV', csv_export(rows), file_name='relink-trajectory.csv',
                           mime='text/csv', key=prefix + '_trajectory_csv', on_click='ignore')
    with st.expander('Completed actions, unmet needs and provenance'):
        st.write('Completed action IDs');st.json(result.completed_actions)
        st.write('Unmet needs');st.json(public_payload(result.unmet_needs))
        st.write('Evaluator metadata');st.json(public_payload(result.run_metadata))
    st.download_button('Download result JSON', json_export(result.model_dump(mode='json')),
        file_name='relink-simulation-result.json', mime='application/json', key=prefix + '_result_json', on_click='ignore')


def render_results(session):
    st.html('<div class="relink-eyebrow">Results</div>')
    st.title('Evidence of recovery.')
    result, issue = current_outcome(session)
    if issue:st.warning(issue)
    if result is None:
        with st.container(border=True):
            st.subheader('No simulation results yet')
            st.write('The independent simulator is not connected or no matching approved simulation has completed.')
            st.caption('No downtime, availability, restoration trajectory, improvement or cost saving is fabricated. '
                       'Planner predictions remain on Planning; saved records are available in History.')
        return
    render_outcome(result, 'current_' + result.plan_id)
