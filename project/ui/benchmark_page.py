"""Benchmark page: shows committed benchmark outputs. Never runs a benchmark or a model."""
import csv
import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

LABELS = {'heuristic': 'Heuristic (no AI)', 'optimizer': 'CP-SAT (no AI)', 'single': 'Single agent',
          'multi': 'Multi-agent', 'no_reviewer': 'Multi, no Reviewer', 'no_feedback': 'Multi, no feedback'}
ORDER = ['optimizer', 'heuristic', 'single', 'multi', 'no_reviewer', 'no_feedback']


def available_runs(root):
    base = Path(root) / 'results' / 'final'
    return sorted((p.parent for p in base.glob('*/summary_report.json')), reverse=True) if base.exists() else []


def load_run(folder):
    folder = Path(folder)
    summary = json.loads((folder / 'summary_report.json').read_text())
    with open(folder / 'per_case.csv', newline='') as stream:
        rows = list(csv.DictReader(stream))
    return summary, rows


def pair(summary, a, b):
    return next((p for p in summary['paired'] if (p['a'], p['b']) == (a, b)), None)


def per_case_long(rows, variants):
    out = []
    for row in rows:
        for v in variants:
            value = row.get(f'{v}_median_downtime')
            if value not in (None, ''):
                out.append({'Case': row['case'], 'Variant': LABELS.get(v, v), 'Weighted downtime': float(value)})
    return out


def _pair_sentence(p, a_label, b_label):
    if p is None:
        return 'Not measured in this run.'
    lo, hi = p['ci95_mean_diff']
    return (f"{a_label} better on **{p['a_better']}**, tie on **{p['ties']}**, worse on **{p['b_better']}** of "
            f"{p['cases']} cases. Mean difference {p['mean_diff']:,.0f} weighted minutes "
            f"(95 % interval {lo:,.0f} to {hi:,.0f}).")


def render_benchmark(root):
    st.html('<div class="relink-eyebrow">Benchmark</div>')
    st.title('What the evidence says.')
    runs = available_runs(root)
    if not runs:
        st.info('No benchmark results found under results/final/. Run the benchmark and the report generator first.')
        return
    folder = st.selectbox('Result set', runs, format_func=lambda p: p.name, key='benchmark_run')
    summary, rows = load_run(folder)
    stats = summary['variants']
    freeze = summary.get('freeze') or {}
    st.caption(f"{summary['cases']} held-out cases · {summary['attempts']} attempts · model `{summary.get('model')}` · "
               f"configuration freeze `{(freeze.get('git_commit_at_freeze') or 'none')[:7]}`. "
               'Synthetic, script-generated cases; not reviewed by a person. Downtime = weighted service-minutes '
               'over 12 hours, measured by the independent simulator (lower is better).')

    no_ai, multi_single, reviewer = pair(summary, 'multi', 'optimizer'), pair(summary, 'multi', 'single'), pair(summary, 'multi', 'no_reviewer')
    a, b, c = st.columns(3)
    with a, st.container(border=True):
        st.markdown('**Agents vs no AI**')
        st.markdown(_pair_sentence(no_ai, 'Multi-agent', 'CP-SAT'))
    with b, st.container(border=True):
        st.markdown('**Multi-agent vs single agent**')
        st.markdown(_pair_sentence(multi_single, 'Multi-agent', 'single'))
        if multi_single and multi_single['ci95_mean_diff'][0] <= 0 <= multi_single['ci95_mean_diff'][1]:
            st.caption('Interval includes zero: no significant difference.')
    with c, st.container(border=True):
        st.markdown('**Is the Reviewer worth it?**')
        st.markdown(_pair_sentence(reviewer, 'With Reviewer', 'without'))

    present = [v for v in ORDER if v in stats]
    st.subheader('Downtime per case')
    shown = st.multiselect('Variants', present, default=[v for v in ('optimizer', 'single', 'multi') if v in present],
                           format_func=LABELS.get, key='benchmark_variants')
    data = pd.DataFrame(per_case_long(rows, shown))
    if not data.empty:
        chart = alt.Chart(data).mark_bar().encode(
            x=alt.X('Case:N', title=None), xOffset='Variant:N',
            y=alt.Y('Weighted downtime:Q', title='Median weighted downtime (lower is better)'),
            color=alt.Color('Variant:N', scale=alt.Scale(scheme='tableau10')),
            tooltip=['Case:N', 'Variant:N', alt.Tooltip('Weighted downtime:Q', format=',.0f')]).properties(height=360)
        st.altair_chart(chart, width='stretch')

    st.subheader('Reliability, cost and safety')
    prices = summary.get('prices')
    table = []
    for v in present:
        s = stats[v]
        row = {'Variant': LABELS.get(v, v), 'Completed': f"{s['completed']}/{s['attempts']}", 'Escalated': s['escalated'],
               'Fact F1': None if s['extraction_f1_initial'] is None else round(s['extraction_f1_initial'], 2),
               'Injection followed': f"{s['injection_followed']}/{s['injection_runs']}" if s['injection_runs'] else '—',
               'Calls': round(s['mean_model_calls'], 1), 'Input tokens': round(s['mean_input_tokens']),
               'Output tokens': round(s['mean_output_tokens']), 'Seconds': round(s['mean_seconds'], 1)}
        if prices:
            row['USD / incident (upper bound)'] = round(s.get('mean_cost_usd', 0), 3)
        table.append(row)
    st.dataframe(table, hide_index=True, width='stretch')
    if prices:
        st.caption(f"Prices: USD {prices['in']} / 1M input and {prices['out']} / 1M output tokens as of {prices['date']}. "
                   'Upper bound: cached input was not recorded separately.')
    completion = pd.DataFrame([{'Variant': LABELS.get(v, v), 'Completed %': 100 * stats[v]['completed'] / stats[v]['attempts']}
                               for v in present])
    st.altair_chart(alt.Chart(completion).mark_bar(cornerRadius=3).encode(
        x=alt.X('Completed %:Q', scale=alt.Scale(domain=[0, 100])), y=alt.Y('Variant:N', sort=None, title=None),
        color=alt.value('#69e3c6'), tooltip=['Variant:N', alt.Tooltip('Completed %:Q', format='.0f')]).properties(height=200),
        width='stretch')

    with st.expander('All paired comparisons'):
        st.dataframe([{'A vs B': f"{LABELS.get(p['a'], p['a'])} vs {LABELS.get(p['b'], p['b'])}", 'Cases': p['cases'],
                       'A better': p['a_better'], 'Tie': p['ties'], 'B better': p['b_better'],
                       'Mean A−B': round(p['mean_diff'] or 0), '95 % CI': f"{p['ci95_mean_diff'][0]:,.0f} to {p['ci95_mean_diff'][1]:,.0f}"}
                      for p in summary['paired']], hide_index=True, width='stretch')
    readme = Path(folder) / 'README.md'
    if readme.exists():
        with st.expander('Written summary and limits'):
            st.markdown(readme.read_text())
