"""Planning controls and real core outputs; only an explicit button starts a run."""
import altair as alt
import pandas as pd
import streamlit as st

from project.auth import can
from project.ui.auth_view import current_user, needs_role

from project.core.tracing import redact
from project.llm.health import preflight
from project.ui.review import render_review
from project.ui.confirmation import render_confirmation
from project.ui.workflow import render_workflow
from project.ui.planning_service import (
    begin_new_attempt, fact_rows, prepare_plan, request_key, schedule_rows, timeline_rows,
)

MODE_LABELS = {'template': 'Offline template baseline', 'single': 'Hosted single agent',
               'multi': 'Hosted multi-agent workflow'}
PLANNER_LABELS = {'cp_sat': 'CP-SAT optimizer', 'greedy': 'Earliest-finish heuristic'}


def _schedule(result):
    if result.plan is None:
        st.info('No candidate schedule is available. Resolve the escalation before trying again.')
        return
    if result.status == 'escalated':
        st.warning('Candidate retained for inspection only. This run did not clear review and cannot be approved.')
    effects=result.metadata.get('decision_effects',[])
    if effects:
        st.warning('Agent-requested action deferrals changed this candidate. Review the reasons and unmet needs before approval.')
        st.dataframe([{'Agent':e['sender'],'Actions':', '.join(e['applied_action_ids']),
                       'Reason':e['request']['reason'],'Evidence':', '.join(e['request']['evidence_ids'])} for e in effects],
                     hide_index=True,width='stretch')
        st.caption('These are conservative model requests, not independently verified operational facts or policy changes.')
    rows = schedule_rows(result)
    if rows:
        st.dataframe(rows, hide_index=True, width='stretch')
        st.caption('Planned actions, not executed work. Work duration excludes travel; routes and timing were checked by the independent validator.')
        data = pd.DataFrame(timeline_rows(result))
        chart = alt.Chart(data).mark_bar(cornerRadius=3).encode(
            x=alt.X('Start:Q', title='Incident minute', scale=alt.Scale(zero=False)),
            x2='End:Q', y=alt.Y('Lane:N', title=None, sort=None),
            color=alt.Color('Stage:N', scale=alt.Scale(domain=['Travel', 'Work'], range=['#74869d', '#69e3c6'])),
            tooltip=['Action:N', 'Target:N', 'Kind:N', 'Stage:N', 'Start:Q', 'End:Q'],
        ).properties(height=max(160, len(rows) * 48))
        st.altair_chart(chart, width='stretch')
    else:
        st.info('The core returned an empty schedule. Review the unmet needs and recorded constraints.')
    st.subheader('Unmet needs')
    if result.plan.unmet_needs:
        for need in result.plan.unmet_needs:
            st.text(need)
    else:
        st.caption('No unmet needs were listed by this plan. This does not establish measured restoration.')
    with st.expander('Scheduler configuration and predictions'):
        st.json(redact(result.plan.planner_config))
        st.caption('Any availability or downtime values here are planner predictions for the encoded static model, not simulator measurements.')
        st.text(result.plan.explanation)


def _evidence(result):
    rows = fact_rows(result)
    if rows:
        st.dataframe(rows, hide_index=True, width='stretch')
    else:
        st.info('No extracted/resolved facts were recorded.')
    st.caption('Resolver status records source/consistency checks, not independent ground-truth confirmation. '
               'The core may retain recognized fixture reports independently of agent extraction. Unknowns remain explicit.')
    if result.state.unresolved_facts:
        st.warning('Unresolved observations require clarification.')
        for unknown in result.state.unresolved_facts:
            st.text(unknown)
    with st.expander('Resolved observations for this run'):
        st.json(result.state.resolved_observations.model_dump())
    with st.expander('Visible report citations'):
        for report in result.state.scenario.reports:
            st.caption(f'{report.report_id} · {report.source_type} · observed {report.observed_at_min} · received {report.received_at_min}')
            st.text(report.text)


def _activity(result):
    if result.mode == 'template':
        st.info('This is deterministic template extraction and scheduling, not a live agent demonstration.')
    if not result.messages:
        st.caption('No coordinator messages were recorded.')
    for index, message in enumerate(result.messages, 1):
        sender = message.get('sender', 'unknown')
        with st.expander(f'{index:02d} · {sender} → {message.get("recipient", "coordinator")} · state {message.get("state_version", "?")}'):
            st.json(redact(message))
    st.caption('Messages are the actual recorded exchanges. The deterministic scheduler is a software tool, not an additional AI agent.')


def _details(result, attempt):
    st.text('Run ID: ' + result.run_id)
    st.text('Scenario: ' + result.state.scenario_id)
    st.text('Mode: ' + MODE_LABELS[result.mode])
    st.text('Transport: ' + result.metadata.get('transport', 'not recorded'))
    st.text('Started (UTC): ' + str(result.metadata.get('started_at_utc', 'not recorded')))
    st.text('Input hash: ' + result.state.source_hash)
    if result.plan:
        st.text('Plan ID: ' + result.plan.plan_id)
    if result.model_usage:
        st.dataframe(redact(result.model_usage), hide_index=True, width='stretch')
        st.caption('Token totals reflect provider-reported usage on recorded responses. Failed requests may have unreported usage. '
                   'API charges are not computed or assumed to be zero.')
    else:
        st.caption('No model requests were recorded for this run.')
    st.json(redact(result.metadata))
    if attempt:
        with st.expander('UI request metadata'):
            st.json(redact(attempt))
    st.caption('Successful/escalated core run records are stored under results/local_runs/. '
               'UI attempt metadata is stored separately under ui_attempts/. These local files are excluded from Git.')


def _result(result, attempt):
    if result.mode == 'template':
        st.caption('OFFLINE TEMPLATE BASELINE · zero hosted inference')
    if result.status == 'awaiting_approval':
        st.success('Candidate generated. Review the operator decision and simulation status below.')
    else:
        st.error('Planning escalated. Operator clarification or a revised request is required.')
    for reason in result.reasons:
        st.text(reason)
    validation = result.validation
    if validation is not None and validation.valid:
        st.info('Independent schedule validation passed for the recorded state.')
    elif validation is not None:
        st.error('Independent schedule validation failed.')
        st.dataframe([item.model_dump() for item in validation.violations], hide_index=True, width='stretch')
    else:
        st.warning('No independently validated schedule is available.')
    for column, label, value in zip(st.columns(4), ('Actions', 'State version', 'Model calls', 'Elapsed'),
        (len(result.plan.actions) if result.plan else 0, result.state.state_version,
         len(result.model_usage), f'{result.metadata.get("duration_seconds", 0):.2f} s')):
        column.metric(label, value)
    schedule, evidence, activity, details = st.tabs(['Schedule', 'Evidence', 'Agent activity', 'Run details'])
    with schedule:
        _schedule(result)
    with evidence:
        _evidence(result)
    with activity:
        _activity(result)
    with details:
        _details(result, attempt)


def render_planning(choice, session, root):
    user = current_user()
    st.html('<div class="relink-eyebrow">Planning workspace</div>')
    st.title('A plan worth reviewing.')
    st.text('Selected incident: ' + choice.scenario.scenario_id)
    if choice.scenario.current_time_min:
        prefix = 'Continuing the same incident' if session.continuation_context is not None else 'Incident clock'
        st.info(f'{prefix} at minute {choice.scenario.current_time_min} of {choice.scenario.horizon_min}. A new plan and fresh approval are required.')
        committed = (session.continuation_context or {}).get('committed_actions', [])
        if committed:
            st.caption('Already-started unaffected work continues under the earlier approval. These crews remain reserved until the listed work end.')
            st.dataframe(committed, hide_index=True, width='stretch')
        if choice.scenario.active_generators:
            st.caption('Running generators: expected expiry comes from the visible inventory specification; fuel is not reset by replanning.')
            st.dataframe([g.model_dump() for g in choice.scenario.active_generators], hide_index=True, width='stretch')
    st.write('Prepare a schedule, inspect its evidence and review the independent checks.')
    # Widget keys are removed when their page is not rendered; retain preferences
    # separately so returning from another view never changes the selected mode.
    if 'planning_mode' not in st.session_state:
        st.session_state['planning_mode'] = session.planning_mode
    if 'planning_scheduler' not in st.session_state:
        st.session_state['planning_scheduler'] = session.planning_scheduler
    left, right = st.columns([1.5, 1])
    with left:
        mode = st.selectbox('Planning mode', list(MODE_LABELS), format_func=MODE_LABELS.get, key='planning_mode')
    with right:
        planner = st.selectbox('Scheduler', list(PLANNER_LABELS), format_func=PLANNER_LABELS.get, key='planning_scheduler')
    session.planning_mode = mode
    session.planning_scheduler = planner
    health = preflight()
    blocked = mode != 'template' and health['status'] == 'blocked'
    if mode == 'template':
        st.caption('Offline fixture-template extraction and real core scheduling. This baseline makes no model requests.')
    else:
        st.caption(f'Hosted provider: {health["provider"]} · Model: {health["model"] or "Not configured"} · Reasoning: {health.get("reasoning_effort") or "Provider default"}')
        st.warning('Generate plan sends the visible synthetic incident to the configured hosted API and can incur charges. '
                   'Selecting this mode alone makes no request.')
        if blocked:
            st.error('Hosted configuration is incomplete. Set the provider, exact model ID and API key locally, then restart the app.')
            for reason in health['reasons']:
                st.text(reason)
    st.caption('Whole-run limits: 12 model calls, 24,000 input / 4,800 output tokens and 180 seconds; each solver attempt ≤5 seconds. '
               'Conservative reservations may stop a run earlier. Failures do not silently switch modes.')
    key = request_key(session, choice, mode, planner)
    attempted = key in session.planning_requests
    start, repeat = st.columns(2)
    with start:
        allowed = can(user, 'generate_plan')
        generate = st.button('Generate plan', key='generate_plan', type='primary',
                             disabled=blocked or session.busy or attempted or not allowed, width='stretch',
                             help=None if allowed else needs_role('generate_plan'))
        if not allowed:
            st.caption('Your role cannot generate plans. ' + needs_role('generate_plan') + '.')
    with repeat:
        if attempted:
            if st.button('Start a new attempt', key='new_planning_attempt', disabled=session.busy, width='stretch'):
                begin_new_attempt(session)
                st.session_state['review_note'] = ''
                st.rerun()
    if generate:
        with st.spinner('Preparing and independently checking the plan…'):
            prepare_plan(session, choice, mode, planner, root, user=user)
        st.rerun()
    if attempted:
        st.caption('This request has already been attempted. Use Start a new attempt for an explicit retry; this clears the old plan, approval and results.')
    attempt = session.planning_attempt
    if attempt:
        for warning in attempt.get('warnings', []):
            st.warning(warning)
        if attempt['status'] in ('failed', 'blocked'):
            st.error('The planning request did not complete. No previous plan or approval remains active.')
            st.text('Failure: ' + attempt.get('error_code', 'unknown') +
                    (' (' + attempt['error_type'] + ')' if attempt.get('error_type') else ''))
            for reason in attempt.get('reasons', []):
                st.text(reason)
            with st.expander('Attempt metadata and any recorded model usage'):
                st.json(redact(attempt))
    result = session.core.current
    if result is not None:
        if attempt and attempt['request_key'] != key:
            st.info('Controls differ from the displayed run. Generate a plan to replace it; no new request has been sent.')
        _result(result, attempt)
    elif not attempt:
        st.info('No plan generated. Choose a mode and scheduler, then explicitly generate a plan.')
    render_workflow(session, choice)
    render_confirmation(choice, session, root)
    render_review(choice, session, root)
