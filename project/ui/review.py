"""Human review controls. Callback arguments bind the previously displayed plan."""
import streamlit as st

from project.auth import PermissionDenied, can
from project.ui.auth_view import current_user, needs_role

from project.core.integration import IntegrationNotReady
from project.core.tracing import redact
from project.ui.review_service import ReviewBlocked, active_approval, record_decision, review_context
from project.ui.simulation_service import simulate_approved


def _decision_callback(session, choice, root, binding, decision):
    try:
        status = record_decision(session, choice, binding, decision,
            st.session_state.get('operator_label', ''), st.session_state.get('review_note', ''), root,
            user=current_user())
        session.review_feedback = {'kind': 'success', 'message':
            'Decision already recorded; no duplicate record created.' if status == 'duplicate' else
            'Approval recorded for simulation only.' if status == 'approve' else
            'Plan rejected. Any previous approval was revoked.'}
    except (ReviewBlocked, PermissionDenied) as error:
        session.review_feedback = {'kind': 'error', 'message': str(error)}
    except Exception as error:
        session.review_feedback = {'kind': 'error', 'message':
            'Decision could not be recorded (' + type(error).__name__ + '). No new approval is active.'}


def _simulation_callback(session, choice, root, binding):
    try:
        status = simulate_approved(session, choice, binding, st.session_state.get('operator_label', ''), root,
                                   user=current_user())
        session.review_feedback = {'kind': 'success' if status in ('completed', 'duplicate') else 'error',
            'message': 'Simulation result recorded. Open Results to inspect evaluator-reported outcomes.' if status == 'completed' else
                       'Simulation was already attempted; it was not run again.' if status == 'duplicate' else
                       'This episode requires unfinished simulator support (dynamic continuation or an exact-horizon event). No measured result was published.' if status == 'unsupported' else
                       'Simulation failed or returned an invalid result. No automatic retry was made; inspect the attempt record.'}
    except (ReviewBlocked, IntegrationNotReady, PermissionDenied) as error:
        session.review_feedback = {'kind': 'error', 'message': str(error)}
    except Exception as error:
        session.review_feedback = {'kind': 'error', 'message': 'Simulation request stopped (' + type(error).__name__ + ').'}


def _continue_callback(session, choice, root):
    from project.ui.continuation import accept_checkpoint
    try:
        accept_checkpoint(session, choice, root, user=current_user())
        st.session_state['review_note'] = ''
    except Exception:
        session.review_feedback = {'kind': 'error', 'message': 'Checkpoint could not be accepted. Refresh and inspect the episode record.'}


def render_review(choice, session, root, part='all'):
    """part: 'decision' (approve/reject), 'simulation' (run/continue) or 'all'."""
    show_decision, show_sim = part in ('all', 'decision'), part in ('all', 'simulation')
    if show_decision:
        st.subheader('Review and approval')
        st.caption('Approval authorizes simulation only. It never dispatches a crew or controls a real network. '
                   'Decisions are recorded under your signed-in identity and role.')
    ready = False;binding = None;reason = None
    try:
        result, binding = review_context(session, choice)
        ready = True
    except ReviewBlocked as error:
        reason = str(error)
    if st.session_state.get('review_note_input_hash') != choice.content_hash:
        st.session_state['review_note'] = ''
        st.session_state['review_note_input_hash'] = choice.content_hash
    operator = st.session_state.get('operator_label', '').strip()
    user = current_user()
    may_approve, may_reject, may_simulate = (can(user, p) for p in ('approve_plan', 'reject_plan', 'simulate'))
    operator_valid = 1 <= len(operator) <= 120
    approved = active_approval(session, choice)
    rejected = bool(ready and session.last_decision and session.last_decision.binding == binding
                    and session.last_decision.approval.decision == 'reject')
    if show_decision:
        if rejected:
            st.error('This plan was rejected. Generate a new plan before requesting approval.')
        elif approved:
            st.success('Approved for simulation by ' + session.core.approval.operator_id + '.')
        elif ready:
            st.info('Awaiting your decision. Inspect the schedule, evidence and validation before approving or rejecting.')
        elif reason:
            st.warning(reason)
        if ready and not operator_valid:
            st.info('Sign in to record a decision.')
        if ready and not may_approve:
            st.info('Your role cannot approve. ' + needs_role('approve_plan') + '. Ask a Restoration Manager to sign in and review this plan.')
        st.text_area('Review note (optional)', key='review_note', max_chars=2000, disabled=not ready or session.busy,
                     placeholder='Reason for the decision, constraints or follow-up needed')
        yes, no = st.columns(2)
        yes.button('Approve plan', key='approve_plan', type='primary', width='stretch',
            disabled=not ready or not operator_valid or approved or rejected or session.busy or not may_approve,
            help=None if may_approve else needs_role('approve_plan'),
            on_click=_decision_callback, args=(session, choice, root, binding, 'approve'))
        no.button('Reject plan', key='reject_plan', width='stretch',
            disabled=not ready or not operator_valid or rejected or session.busy or not may_reject,
            help='Rejecting an already approved plan revokes its approval.' if may_reject else needs_role('reject_plan'),
            on_click=_decision_callback, args=(session, choice, root, binding, 'reject'))
        feedback = session.review_feedback
        if feedback:
            (st.success if feedback['kind'] == 'success' else st.error)(feedback['message'])
        record = session.last_decision
        if record:
            with st.expander('Recorded operator decision'):
                st.json(redact(record.model_dump(mode='json')))
                st.caption('Record ID: ' + record.decision_id + ' · Stored locally under results/local_runs/decisions/. '
                           'Changing the plan, state or incident invalidates its approval.')
    if not show_sim:
        return
    st.subheader('Approved simulation')
    connected = session.core.simulator is not None
    if not connected:
        st.info('Independent simulator not connected. Approval can be recorded, but simulation remains disabled until Zahra’s evaluator is integrated.')
    else:
        st.caption('Connected implementation: ' + (session.simulator_label or 'Application callback'))
    already = bool(session.core.approval and session.core.approval.plan_hash in session.simulation_requests)
    same_operator = bool(approved and operator == session.core.approval.operator_id)
    if approved and operator_valid and not same_operator:
        st.warning('Only the approver can start simulation of this approval.')
    st.button('Simulate approved plan', key='simulate_plan', width='stretch',
        disabled=not connected or not approved or not same_operator or already or session.busy or not may_simulate,
        on_click=_simulation_callback, args=(session, choice, root, binding))
    if connected:
        st.caption('Incident events pause execution. Accept the visible update, generate a new plan and approve it before continuing.')
    if session.simulation_attempt:
        attempt = session.simulation_attempt
        if attempt['status'] == 'completed':
            paused = bool(session.simulation_result and session.simulation_result.run_metadata.get('replan_required'))
            if paused:
                st.warning('Incident paused at a resource update. Results cover elapsed time only; the full horizon is not yet measured.')
                st.button('Accept event update and replan', key='accept_event_update',
                          disabled=session.busy or not can(user, 'continue_incident'),
                          help=None if can(user, 'continue_incident') else needs_role('continue_incident'),
                          on_click=_continue_callback, args=(session, choice, root))
            else:
                st.success('Independent incident result recorded. No new simulation occurs on rerender.')
        elif attempt['status'] == 'unsupported':
            st.warning('Simulator support is pending for this episode. No result was published and no automatic retry will run.')
        elif attempt['status'] == 'failed':
            st.error('The simulation attempt did not produce an accepted result. Generate a fresh plan after investigating; this attempt will not run again automatically.')
        with st.expander('Simulation attempt record'):
            st.json(redact(attempt))
