"""Recorded human decisions bound to the exact displayed run, plan and state."""
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import Field
from project.core.schemas import Approval, Contract
from project.core.coordinator import approve, approve_run, check_approval
from project.core.state import digest
from project.core.validator import validate
from project.ui.local_records import save_record
from project.ui.catalog import load_catalog


class ReviewBlocked(ValueError):
    """Only application-authored, credential-safe messages belong here."""


class DecisionRecord(Contract):
    decision_id: str
    session_id: str
    run_id: str
    scenario_id: str
    input_hash: str
    binding: str
    approval: Approval
    note: str = Field(default='', max_length=2000)
    recorded_at_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    authenticated: bool = False


def review_context(session, choice):
    result = session.core.current
    if session.busy:
        raise ReviewBlocked('Wait for the current operation to finish.')
    if result is None or result.plan is None:
        raise ReviewBlocked('Generate a current plan before reviewing it.')
    if (session.selected_key, session.scenario_hash) != (choice.key, choice.content_hash):
        raise ReviewBlocked('The selected incident changed. Generate a new plan.')
    if digest(choice.scenario) != choice.content_hash or result.state.source_hash != choice.content_hash:
        raise ReviewBlocked('Incident content changed. Generate a new plan.')
    if digest(result.state.scenario) != choice.content_hash or result.state.scenario_id != choice.scenario.scenario_id:
        raise ReviewBlocked('Plan and incident do not match. Generate a new plan.')
    if result.status != 'awaiting_approval' or result.validation is None or not result.validation.valid:
        raise ReviewBlocked('An escalated or unvalidated run cannot be approved.')
    if not validate(result.plan, result.state).valid:
        raise ReviewBlocked('Current plan validation failed. Generate a corrected plan.')
    binding = digest({'run': result.run_id, 'input': choice.content_hash,
                      'plan': digest(result.plan), 'state': digest(result.state)})
    previous = session.last_decision
    if previous and previous.run_id == result.run_id and previous.binding != binding:
        raise ReviewBlocked('Plan or state changed after review. Generate a new plan.')
    return result, binding


def ensure_current_source(session, choice, root):
    # Button callbacks run before Streamlit rerenders/reloads the catalog. Check
    # disk freshness here too, rather than trusting the last displayed object.
    if not any(item.key == choice.key and (item.content_hash == (session.source_hash or choice.content_hash))
               for item in load_catalog(root).choices):
        session.core.approval = None
        raise ReviewBlocked('The selected input file changed or is no longer available. Refresh and generate a new plan.')


def active_approval(session, choice):
    try:
        result, binding = review_context(session, choice)
        record = session.last_decision
        if record is None or record.binding != binding or record.approval.decision != 'approve':
            return False
        if session.core.approval is None or digest(record.approval) != digest(session.core.approval):
            return False
        check_approval(session.core.approval, result.plan, result.state)
        return True
    except (ValueError, TypeError):
        return False


def record_decision(session, choice, expected_binding, decision, operator_id, note, root):
    if decision not in ('approve', 'reject'):
        raise ReviewBlocked('Choose approve or reject.')
    if not isinstance(operator_id, str) or not 1 <= len(operator_id.strip()) <= 120:
        raise ReviewBlocked('Enter an operator label of 1–120 characters in the sidebar.')
    if not isinstance(note, str) or len(note) > 2000:
        raise ReviewBlocked('Review notes must be at most 2,000 characters.')
    result, binding = review_context(session, choice)
    ensure_current_source(session, choice, root)
    if binding != expected_binding:
        session.core.approval = None
        raise ReviewBlocked('The displayed plan changed before the decision. Review a new plan.')
    previous = session.last_decision
    if previous and previous.run_id == result.run_id:
        if previous.approval.decision == 'reject':
            if decision == 'reject':
                return 'duplicate'
            raise ReviewBlocked('This plan was rejected. Generate a new plan before approval.')
        if decision == 'approve' and active_approval(session, choice):
            return 'duplicate'
    # Fail closed: a replacement/rejection revokes prior approval before writing.
    session.core.approval = None
    approval = (approve_run(result, operator_id.strip()) if decision == 'approve' else
                approve(result.plan.plan_id, result.state.state_version, 'reject',
                        plan=result.plan, state=result.state, operator_id=operator_id.strip()))
    record = DecisionRecord(decision_id=str(uuid4()), session_id=session.session_id,
        run_id=result.run_id, scenario_id=result.state.scenario_id, input_hash=choice.content_hash,
        binding=binding, approval=approval, note=note.strip())
    # No active decision unless the audit write succeeds.
    save_record(Path(root) / 'results/local_runs/decisions', record.decision_id, record.model_dump(mode='json'))
    session.core.approval = approval
    session.last_decision = record
    session.decision_history.append(record)
    session.simulation_result = None
    return decision
