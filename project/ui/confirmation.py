"""Explicit, auditable human clarification. Rendering never changes evidence."""
import streamlit as st

from project.ui.confirmation_service import confirm_fact, confirmation_binding, fact_options
from project.ui.review_service import ReviewBlocked

VALUES = {'Choose a verified value': None, 'True — working / available / open': True,
          'False — failed / unavailable / closed': False}


def _submit(session,choice,root,binding,options):
    try:
        target=options[st.session_state['confirmation_target']]
        status=confirm_fact(session,choice,binding,*target,
            VALUES[st.session_state['confirmation_value']],st.session_state.get('operator_label',''),
            st.session_state['confirmation_source'],st.session_state['confirmation_note'],
            st.session_state['confirmation_ack'],root)
        session.confirmation_feedback={'ok':True,'message':
            'Confirmation already recorded; no duplicate update created.' if status=='duplicate' else
            'Confirmation recorded. The earlier plan and approval were cleared. Generate a new plan and review it again.'}
    except ReviewBlocked as error:
        session.confirmation_feedback={'ok':False,'message':str(error)}
    except Exception:
        session.confirmation_feedback={'ok':False,'message':
            'Confirmation could not be recorded. No new evidence was activated; inspect the audit storage and refresh.'}


def render_confirmation(choice,session,root):
    with st.expander('Record operator clarification'):
        st.caption('Use verified operational evidence to resolve missing or contradictory facts. '
                   'This records your assertion; the app does not independently verify it or authenticate your operator label. '
                   'Confirmation never approves or executes a plan.')
        if session.confirmation_feedback:
            feedback=session.confirmation_feedback
            (st.success if feedback['ok'] else st.error)(feedback['message'])
        if session.confirmation_history:
            st.caption(f'{len(session.confirmation_history)} confirmation(s) recorded in this incident. '
                       'Original reports are retained; corrections explicitly supersede earlier confirmations of the same fact.')
        if st.session_state.get('confirmation_input_hash')!=choice.content_hash:
            for key in ('confirmation_target','confirmation_value','confirmation_source','confirmation_note','confirmation_ack'):
                st.session_state.pop(key,None)
            st.session_state['confirmation_input_hash']=choice.content_hash
        try:
            binding=confirmation_binding(session,choice)
        except ReviewBlocked as error:
            st.info(str(error));return
        options=fact_options(choice.scenario)
        st.caption(f'Confirmation applies at incident minute {choice.scenario.current_time_min}. '
                   'A later physical repair can establish a new state; verification does not change simulator truth.')
        with st.form('operator_confirmation_form'):
            st.selectbox('Fact to confirm',list(options),key='confirmation_target')
            st.selectbox('Verified value',list(VALUES),key='confirmation_value')
            st.text_input('Verification source',key='confirmation_source',max_chars=500,
                          placeholder='For example: named field update or operator inspection reference')
            st.text_area('Verification reason and details',key='confirmation_note',max_chars=2000)
            st.checkbox('I verified this fact using the source stated above',key='confirmation_ack')
            st.form_submit_button('Record confirmation and invalidate plan',
                disabled=session.busy,on_click=_submit,args=(session,choice,root,binding,options))
