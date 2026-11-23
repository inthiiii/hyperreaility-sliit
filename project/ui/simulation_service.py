"""Approved, typed simulator boundary. No simulator implementation or truth loader."""
from datetime import datetime, timezone
import math
from pathlib import Path
from uuid import uuid4

from project.core.coordinator import check_approval
from project.core.integration import IntegrationNotReady
from project.core.schemas import SimulationResult
from project.core.state import digest
from project.ui.local_records import save_record
from project.ui.review_service import ReviewBlocked, active_approval, review_context, ensure_current_source


def attach_simulator(session, callback, label):
    """Called only by application integration code, never from user-provided imports."""
    if session.busy:
        raise ReviewBlocked('Wait for the current operation before connecting a simulator.')
    if not callable(callback) or not isinstance(label, str) or not label.strip():
        raise ValueError('Provide a callable simulator and a descriptive implementation label')
    session.core.simulator = callback
    session.simulator_label = label.strip()


def simulate_approved(session, choice, expected_binding, operator_id, root):
    result, binding = review_context(session, choice)
    ensure_current_source(session, choice, root)
    if expected_binding != binding or not active_approval(session, choice):
        raise ReviewBlocked('Current matching operator approval is required for simulation.')
    if not isinstance(operator_id, str) or operator_id.strip() != session.core.approval.operator_id:
        raise ReviewBlocked('Use the operator label recorded on the approval.')
    if session.core.simulator is None:
        raise IntegrationNotReady('Awaiting Zahra independent simulator integration')
    key = session.core.approval.plan_hash
    if key in session.simulation_requests:
        return 'duplicate'
    session.simulation_requests.add(key)
    session.simulation_result = None
    attempt = {'attempt_id': str(uuid4()), 'run_id': result.run_id, 'binding': binding,
               'plan_hash': key, 'scenario_id': result.state.scenario_id,
               'state_version': result.state.state_version, 'operator_id': operator_id.strip(),
               'simulator': session.simulator_label or 'Injected callback',
               'started_at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'starting'}
    session.simulation_attempt = attempt
    directory = Path(root) / 'results/local_runs/simulation_attempts'
    session.busy = True
    try:
        # Audit-start failure must prevent callback execution.
        save_record(directory, attempt['attempt_id'], attempt)
        raw = session.core.simulate()
        simulation = SimulationResult.model_validate(raw)
        if (simulation.scenario_id, simulation.plan_id, simulation.state_version) != (
                result.state.scenario_id, result.plan.plan_id, result.state.state_version):
            raise ValueError('Simulator output does not match the approved plan/state')
        if len(set(simulation.completed_actions)) != len(simulation.completed_actions) or not set(simulation.completed_actions) <= {a.action_id for a in result.plan.actions}:
            raise ValueError('Invalid completed action IDs')
        if any(value is not None and not math.isfinite(value) for value in simulation.metrics.values()):
            raise ValueError('Non-finite simulation metric')
        # Recheck after callback; copied arguments cannot change the live approval.
        ensure_current_source(session, choice, root)
        check_approval(session.core.approval, result.plan, result.state)
        attempt.update(status='completed', finished_at_utc=datetime.now(timezone.utc).isoformat(),
                       result=simulation.model_dump(mode='json'), result_hash=digest(simulation))
        save_record(directory, attempt['attempt_id'], attempt)
        session.simulation_result = simulation
        return 'completed'
    except Exception as error:
        session.simulation_result = None
        attempt.pop('result', None);attempt.pop('result_hash', None)
        attempt.update(status='failed', error_type=type(error).__name__,
                       finished_at_utc=datetime.now(timezone.utc).isoformat())
        try:
            save_record(directory, attempt['attempt_id'], attempt)
        except Exception:
            attempt['audit_warning'] = 'Simulation attempt record could not be saved.'
        return 'failed'
    finally:
        session.busy = False
