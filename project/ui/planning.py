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
from project.ui.agent_flow import LiveFlow, final_state, replay
from project.ui.agent_view import collaboration_counts, conversation_rows, gantt_rows, inbox
from project.ui.review_service import active_approval
from project.ui.priority_service import proposal_key, record_priority_decision
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
        st.subheader('Crew and generator timeline')
        data = pd.DataFrame(gantt_rows(result))
        chart = alt.Chart(data).mark_bar(cornerRadius=3).encode(
            x=alt.X('Start:Q', title='Incident minute', scale=alt.Scale(domain=[result.state.scenario.current_time_min,
                                                                                result.state.scenario.horizon_min])),
            x2='End:Q', y=alt.Y('Lane:N', title=None, sort=None),
            color=alt.Color('Stage:N', scale=alt.Scale(domain=['Travel', 'Work', 'Powering site'],
                                                      range=['#74869d', '#69e3c6', '#f1cb78'])),
            tooltip=['Lane:N', 'Action:N', 'Stage:N', 'Start:Q', 'End:Q'],
        ).properties(height=max(140, data['Lane'].nunique() * 56))
        st.altair_chart(chart, width='stretch')
        st.caption('Planned timing (prediction). Generator bars end when its configured fuel autonomy runs out.')
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
        return
    st.markdown('**Agent workflow**')
    slot = st.empty()
    if st.button('▶ Replay the agent run', key='replay_agents',
                 help='Steps through the recorded messages again. No model is called.'):
        replay(slot, result)
    else:
        slot.html(final_state(result).html())
    counts = collaboration_counts(result)
    for column, label in zip(st.columns(5), ('agents', 'messages', 'challenges', 'holds', 'schedules')):
        column.metric(label.title(), counts[label])
    rows = conversation_rows(result)
    kinds = sorted({r['Kind'] for r in rows})
    chosen = st.multiselect('Show', kinds, default=kinds, key='conversation_kinds')
    st.dataframe([r for r in rows if r['Kind'] in chosen], hide_index=True, width='stretch',
                 column_config={'Summary': st.column_config.TextColumn(width='large')})
    st.caption('Summaries of the recorded messages. Challenges from the Plan Reviewer go back to the Network '
               'Investigator, and every new schedule comes from CP-SAT (software, not an AI agent).')
    with st.expander('Raw recorded messages'):
        _raw_messages(result)


def _raw_messages(result):
    for index, message in enumerate(result.messages, 1):
        sender = message.get('sender', 'unknown')
        st.caption(f'{index:02d} · {sender} → {message.get("recipient", "coordinator")} · state {message.get("state_version", "?")}')
        st.json(redact(message), expanded=False)
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


def _result(result, attempt, choice=None):
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
    box = inbox(result)
    inbox_label = f"Operator inbox ({len(box['questions']) + len(box['proposals'])})"
    schedule, evidence, activity, operator, details = st.tabs(['Schedule', 'Evidence', 'Agent conversation', inbox_label, 'Run details'])
    with schedule:
        _schedule(result)
    with evidence:
        _evidence(result)
    with activity:
        _activity(result)
    with operator:
        _inbox(result, box, choice)
    with details:
        _details(result, attempt)


def _decide(session, result, index, decision, root):
    try:
        record_priority_decision(session, result, index, decision, st.session_state.get(f'proposal_note_{index}', ''),
                                 root, user=current_user())
    except Exception as error:  # noqa: BLE001 - surfaced to the operator
        st.session_state['priority_feedback'] = f'Not recorded: {error}'


def _inbox(result, box, choice=None):
    from project.ui.inbox_answer import render_questions
    from project.ui.session import get_dashboard_session
    session = get_dashboard_session(st.session_state)
    root = st.session_state.get('relink_root')
    st.subheader('Questions for the operator')
    render_questions(choice, session, root, box['questions'])
    st.subheader('Priority proposals')
    if not box['proposals']:
        st.caption('No proposals. Agents may only propose priority changes; weights stay as approved.')
    allowed = can(current_user(), 'decide_priority')
    for index, proposal in enumerate(box['proposals']):
        with st.container(border=True):
            st.markdown(f"**{proposal['service_id']}** → {'critical' if proposal['proposed_critical'] else 'standard'} "
                        f"· from {proposal.get('source', '').replace('_', ' ')}")
            st.write(proposal['reason'])
            st.caption('Evidence: ' + ', '.join(proposal['evidence_ids']))
            decided = session.priority_decisions.get(proposal_key(result, index))
            if decided:
                st.info(f"{decided['decision'].title()}ed by {decided['decided_by']}. {decided['effect']}")
                continue
            st.text_input('Note', key=f'proposal_note_{index}', disabled=not allowed)
            accept, reject = st.columns(2)
            accept.button('Accept as policy request', key=f'accept_proposal_{index}', disabled=not allowed or root is None,
                          on_click=_decide, args=(session, result, index, 'accept', root))
            reject.button('Reject proposal', key=f'reject_proposal_{index}', disabled=not allowed or root is None,
                          on_click=_decide, args=(session, result, index, 'reject', root))
            if not allowed:
                st.caption(needs_role('decide_priority'))
    if st.session_state.get('priority_feedback'):
        st.error(st.session_state.pop('priority_feedback'))
    if box['ignored']:
        st.subheader('Reports the agents set aside')
        st.dataframe([{'Report': i['report_id'], 'Why': i['kind'].replace('_', ' '), 'Note': i.get('note', '')}
                      for i in box['ignored']], hide_index=True, width='stretch')
        st.caption('Instruction attempts are flagged and never acted on. Check that nothing important was ignored.')


def render_planning(choice, session, root):
    user = current_user()
    st.session_state['relink_root'] = str(root)
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
    st.write('Prepare a schedule, inspect its evidence, approve it and measure the outcome.')
    render_workflow(session, choice)
    labels = ['① Generate', '② Inspect plan', '③ Review & approve', '④ Simulate']
    step_generate, step_inspect, step_review, step_simulate = st.tabs(labels, default=labels[_current_step(session, choice)])
    with step_generate:
        _generate_step(choice, session, root, user)
    with step_inspect:
        _inspect_step(choice, session)
    with step_review:
        render_confirmation(choice, session, root)
        render_review(choice, session, root, part='decision')
    with step_simulate:
        render_review(choice, session, root, part='simulation')


def _current_step(session, choice):
    result = session.core.current
    if result is None or result.state.source_hash != choice.content_hash:
        return 0
    if session.simulation_result is not None or active_approval(session, choice):
        return 3
    return 2 if result.status == 'awaiting_approval' else 1


def _generate_step(choice, session, root, user):
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
    if st.session_state.pop('auto_replan', False) and not generate:
        if blocked or session.busy or attempted or not allowed:
            st.warning('Your answer was recorded, but a new plan could not start automatically. Use Generate plan.')
        else:
            st.info('Replanning with your answer as new evidence…')
            generate = True
    if generate:
        st.markdown('**Live agent workflow**')
        flow = LiveFlow(st.empty(), mode, len(choice.scenario.reports))
        with st.spinner('Agents are working on the incident…'):
            prepare_plan(session, choice, mode, planner, root, user=user, progress=flow)
        flow.finish(session.core.current)
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
    if session.core.current is not None and session.core.current.status != 'awaiting_approval':
        st.warning('Planning escalated: some facts could not be established. Answer the open questions in '
                   '② Inspect plan → Operator inbox; each answer starts a new plan.')
    elif session.core.current is not None:
        st.success('A plan is ready. Open ② Inspect plan, then ③ Review & approve.')
        if session.core.current.state.source_hash == choice.content_hash:
            st.markdown('**How this plan was made**')
            st.html(final_state(session.core.current).html())


def _inspect_step(choice, session):
    attempt = session.planning_attempt
    result = session.core.current
    key = request_key(session, choice, session.planning_mode, session.planning_scheduler)
    if result is not None:
        if attempt and attempt['request_key'] != key:
            st.info('Controls differ from the displayed run. Generate a plan to replace it; no new request has been sent.')
        _result(result, attempt, choice)
    elif not attempt:
        st.info('No plan generated yet. Use ① Generate.')
