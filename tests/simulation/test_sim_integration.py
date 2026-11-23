"""End-to-end with Ihthisham's merged core (template mode, no model calls)."""
import pytest

pytest.importorskip('ortools')

from project.core.coordinator import Coordinator  # noqa: E402
from project.core.integration import CoreSession  # noqa: E402
from project.data.evaluator import EvaluatorLoader  # noqa: E402
from project.data.loader import CaseLoader  # noqa: E402
from project.simulation.engine import SimulationRejected, session_callback  # noqa: E402


def prepared(case='demo/DEMO-005.json', approve=True):
    scenario = CaseLoader().load_case(case)
    session = CoreSession()
    session.simulator = session_callback(session, EvaluatorLoader())
    result = session.prepare(Coordinator(), scenario, 'template')
    if approve:
        session.approve('test-operator')
    return session, result


def test_core_plan_simulated_independently():
    session, run = prepared()
    assert run.status == 'awaiting_approval'
    sim = session.simulate()
    assert sim.plan_id == run.plan.plan_id and sim.state_version == run.state.state_version
    assert sim.metrics['weighted_downtime_min'] < sim.metrics['baseline_weighted_downtime_min']
    assert sim.run_metadata['planner_prediction_used'] is False
    # Planner's own prediction is recorded separately and is not used as the measurement.
    print('planner config prediction keys:', sorted(k for k in run.plan.planner_config if 'predict' in k))
    print('measured metrics:', sim.metrics)


def test_unapproved_session_cannot_simulate():
    session, _ = prepared(approve=False)
    with pytest.raises(ValueError):
        session.simulate()


def test_stale_approval_rejected_by_simulator_itself():
    session, run = prepared()
    stale = session.approval.model_copy(update={'state_version': run.state.state_version + 1})
    session.approval = stale
    with pytest.raises(Exception):      # CoreSession or simulator must refuse
        session.simulate()
    from project.simulation.engine import simulate
    with pytest.raises(SimulationRejected):
        simulate(run.state.scenario, run.plan, stale, EvaluatorLoader().load('DEMO-005'), state=run.state)
