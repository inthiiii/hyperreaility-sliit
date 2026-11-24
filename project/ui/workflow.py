"""Read-only operator guidance derived from the current incident and audit state."""
from dataclasses import dataclass

from project.ui.outcome_data import current_outcome
from project.ui.review_service import active_approval


@dataclass(frozen=True)
class WorkflowStatus:
    code: str
    title: str
    detail: str
    next_step: str
    level: str = 'info'


def workflow_status(session, choice):
    if choice is None:
        return WorkflowStatus('no_incident', 'Select an incident',
            'No validated incident is selected.', 'Choose a demo or development scenario.')
    if session.busy:
        return WorkflowStatus('busy', 'Operation in progress',
            'The current request is running.', 'Wait for it to finish before starting another request.')
    run = session.core.current
    if run is None:
        attempt = session.planning_attempt
        if attempt and attempt.get('status') in ('failed', 'blocked'):
            return WorkflowStatus('planning_failed', 'Planning did not complete',
                'There is no active plan or approval.',
                'Review the planning error, correct its cause, then explicitly start a new attempt.', 'warning')
        return WorkflowStatus('ready', 'Ready to plan',
            'No recovery plan has been generated for this incident.',
            'Open Planning, choose a mode and generate a plan.')
    if run.status == 'escalated':
        return WorkflowStatus('escalated', 'Clarification required',
            'The run did not clear planning/review checks. Approval and simulation are blocked.',
            'Inspect the recorded reasons and Evidence tab. Obtain verified clarification before generating a new plan.', 'warning')
    decision = session.last_decision
    if decision and decision.run_id == run.run_id and decision.approval.decision == 'reject':
        return WorkflowStatus('rejected', 'Plan rejected',
            'This plan cannot be approved again or simulated.',
            'Review the rejection note and explicitly start a new planning attempt.', 'warning')
    outcome, issue = current_outcome(session)
    if outcome is not None:
        if outcome.run_metadata.get('replan_required'):
            return WorkflowStatus('replan_required', 'Replanning required',
                'The evaluator reported a change requiring a new reviewed plan.',
                'Retain this result as history. Accept the event update on Planning, generate a new plan and obtain fresh approval before continuing.', 'warning')
        return WorkflowStatus('completed', 'Simulation recorded',
            'The current plan has a matching evaluator result.',
            'Open Results to inspect service intervals and measurements, or History to export the recorded run.', 'success')
    if issue:
        return WorkflowStatus('invalid_result', 'Stored result cannot be used', issue,
            'Inspect the saved records and generate a fresh plan after resolving the mismatch.', 'warning')
    attempt = session.simulation_attempt
    if attempt and attempt.get('status') in ('unsupported', 'failed'):
        unsupported = attempt['status'] == 'unsupported'
        return WorkflowStatus('unsupported' if unsupported else 'simulation_failed',
            'Episode support pending' if unsupported else 'Simulation did not complete',
            'No measured result was published. This attempt will not automatically run again.',
            'Inspect the episode record and supported scenario contract before retrying.'
            if unsupported else 'Inspect the attempt record, resolve the failure and explicitly generate a new plan.', 'warning')
    if active_approval(session, choice):
        if session.core.simulator is None:
            return WorkflowStatus('backend_pending', 'Approved · awaiting simulator',
                'Your decision is recorded, but the simulator backend is not connected.',
                'Wait for backend integration. No measured recovery results are available yet.')
        return WorkflowStatus('approved', 'Ready to simulate',
            'The current plan has matching recorded operator approval.',
            'Use the approving operator label and click Simulate approved plan on Planning.')
    if decision and decision.approval.decision == 'approve':
        return WorkflowStatus('approval_expired', 'Approval is no longer current',
            'The current plan/state does not match the recorded approval.',
            'Generate a new plan and review it again before simulation.', 'warning')
    return WorkflowStatus('review', 'Awaiting operator review',
        'A candidate plan is available; no simulation is authorized yet.',
        'Inspect the schedule, evidence and validator, then approve or reject on Planning.')


def render_workflow(session, choice):
    import streamlit as st
    status = workflow_status(session, choice)
    with st.container(border=True):
        st.subheader(status.title)
        getattr(st, status.level)(status.detail)
        st.caption('Next: ' + status.next_step)
