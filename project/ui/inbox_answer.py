"""Answer an agent question in place: records operator evidence, then replans."""
import re

import streamlit as st

from project.auth import PermissionDenied, can
from project.ui.auth_view import current_user, needs_role
from project.ui.confirmation_service import confirm_fact, confirmation_binding, fact_options
from project.ui.review_service import ReviewBlocked

ANSWERS = {'Yes: working / available / open': True, 'No: failed / unavailable / closed': False}
ATTR = {'equipment_ok': 'equipment working', 'grid_power_ok': 'grid power on', 'backhaul_ok': 'backhaul link working',
        'open': 'road open'}


def relevant_options(scenario, target_id):
    options = fact_options(scenario)
    match = {k: v for k, v in options.items() if v[1] == target_id}
    return match or options


def label(option):
    kind, target, attribute = option.split(':')
    return f'{target} · {ATTR.get(attribute, attribute)}?'


def form_id(question):
    """Stable per question (not per list position), so answers never carry over to another question."""
    raw = question.get('fact') or f"{question.get('target_id')}-{question.get('question')}"
    return re.sub(r'[^A-Za-z0-9_]+', '_', raw)[:80]


def _record(session, choice, root, binding, question, index, options):
    user = current_user()
    try:
        fact = st.session_state[f'answer_fact_{index}']
        status = confirm_fact(session, choice, binding, *options[fact], ANSWERS[st.session_state[f'answer_value_{index}']],
                              st.session_state.get('operator_label', ''),
                              st.session_state.get(f'answer_source_{index}') or 'Operator answer in the RE:L!NK inbox',
                              f"Answer to agent question about {question.get('target_id')}: {question.get('question')}",
                              st.session_state.get(f'answer_ack_{index}') is True, root, user=user)
        replan = can(user, 'generate_plan')
        if status == 'recorded' and replan:
            st.session_state['auto_replan'] = True
        st.session_state['inbox_feedback'] = (True, 'Answer recorded as new evidence. ' +
                                              ('Replanning now on ① Generate.' if replan else
                                               'A NOC Coordinator must generate a new plan.'))
    except (ReviewBlocked, PermissionDenied) as error:
        st.session_state['inbox_feedback'] = (False, str(error))


def render_questions(choice, session, root, questions):
    user = current_user()
    feedback = st.session_state.pop('inbox_feedback', None)
    if feedback:
        (st.success if feedback[0] else st.error)(feedback[1])
    if not questions:
        st.caption('No open questions. Unknown facts would appear here instead of stopping the run.')
        return
    allowed = can(user, 'confirm_fact')
    binding = None
    if allowed and choice is not None:
        try:
            binding = confirmation_binding(session, choice)
        except ReviewBlocked as error:
            st.caption(str(error))
    for q in questions:
        index = form_id(q)
        with st.container(border=True):
            st.markdown(f"**{q.get('target_id')}** · {q.get('question')}")
            st.caption(f"From {q.get('source', 'an agent').replace('_', ' ')} · evidence "
                       f"{', '.join(q.get('evidence_ids', [])) or 'none cited'}")
            if not allowed:
                st.caption(needs_role('confirm_fact'))
                continue
            if binding is None or choice is None:
                continue
            options = relevant_options(choice.scenario, q.get('target_id'))
            if q.get('fact') in options:
                options = {q['fact']: options[q['fact']]}
            with st.form(f'answer_form_{index}', clear_on_submit=True):
                st.selectbox('Which fact', list(options), format_func=label, key=f'answer_fact_{index}')
                st.radio('Answer', list(ANSWERS), key=f'answer_value_{index}', horizontal=True)
                st.text_input('How you know', key=f'answer_source_{index}', max_chars=500,
                              placeholder='For example: phone call with the C1 crew lead')
                st.checkbox('I verified this answer', key=f'answer_ack_{index}')
                st.form_submit_button('Record answer and replan' if can(user, 'generate_plan') else 'Record answer',
                                      type='primary', on_click=_record,
                                      args=(session, choice, root, binding, q, index, options))
    st.caption('Your answer becomes confirmed operator evidence (kept in History). It clears the current plan and '
               'approval; a NOC Coordinator\'s answer immediately starts a new plan with the same mode.')
