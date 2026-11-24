"""Optional application composition; evaluator truth is loaded only on execution."""
from importlib import import_module
from pathlib import Path

from project.core.integration import IntegrationNotReady
from project.core.state import digest
from project.ui.simulation_service import attach_simulator

LABEL = 'Zahra independent simulator · static episodes'

# Units are defined by the version 0.1 simulator, not inferred from metric values.
METRIC_UNITS = {
    'horizon_min': 'incident minutes', 'services_total': 'services',
    'total_weighted_horizon_min': 'weighted service-minutes',
    'weighted_available_min': 'weighted service-minutes',
    'weighted_downtime_min': 'weighted service-minutes',
    'unweighted_availability': 'fraction (0–1)',
    'critical_service_downtime_min': 'critical service-minutes',
    'first_restoration_min': 'incident minutes',
    'services_available_at_horizon_end': 'services', 'unmet_needs_count': 'services',
    'baseline_weighted_downtime_min': 'weighted service-minutes',
    'weighted_downtime_reduction_min': 'weighted service-minutes',
    'actions_completed': 'actions', 'actions_not_completed': 'actions',
}


def connect_static_backend(session, choice, root):
    """Attach per-CoreSession; passive rendering never loads truth or simulates."""
    if session.core.simulator is not None:
        return True
    if session.busy or choice.source != 'processed_input':
        return False
    root = Path(root).resolve()
    try:
        engine = import_module('project.simulation.engine')
        evaluator = import_module('project.data.evaluator')
        loader = import_module('project.data.loader')
    except ImportError:
        return False  # Data-only main remains usable before the simulator merges.
    core = session.core

    def callback(state, plan):
        # Revalidate the selected visible source; do not substitute fixture truth.
        visible = loader.CaseLoader(root / 'data/processed/agent_inputs').load_case(
            root / choice.key)
        if digest(visible) != digest(state.scenario):
            raise ValueError('Selected scenario changed before simulation')
        truth = evaluator.EvaluatorLoader(root / 'data/evaluation/ground_truth').load(state.scenario_id)
        if truth.future_events or state.scenario.current_time_min != 0:
            raise IntegrationNotReady('Dynamic continuation is pending; this milestone supports static episodes only')
        # Version 0.1 reports the pre-horizon state for events exactly at the horizon.
        # Block affected runs until the backend corrects that boundary behavior.
        generators = {g.generator_id: g for g in truth.generators}
        for action in plan.actions:
            if action.work_end_min == state.scenario.horizon_min or (
                    action.kind == 'generator_deploy' and
                    action.work_end_min + generators[action.generator_id].autonomy_minutes == state.scenario.horizon_min):
                raise IntegrationNotReady('Exact-horizon event support awaits the simulator boundary fix')
        result = engine.simulate(state.scenario, plan, core.approval, truth, state=state)
        metadata = dict(result.run_metadata)
        metadata.update(metric_units=METRIC_UNITS, integration_scope='static_episode',
                        evaluator_truth_hash=digest(truth))
        return result.model_copy(update={'run_metadata': metadata})

    attach_simulator(session, callback, LABEL)
    return True
