"""Optional application composition; evaluator truth is loaded only on execution."""
from importlib import import_module
from pathlib import Path

from project.core.integration import IntegrationNotReady
from project.core.state import digest
from project.ui.simulation_service import attach_simulator

LABEL = 'Zahra independent simulator · event checkpoints and approved continuation'

# Units are defined by the version 0.1 simulator, not inferred from metric values.
METRIC_UNITS = {
    'measured_duration_min': 'incident minutes',
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
    'observed_until_min': 'incident minutes', 'incident_horizon_min': 'incident minutes',
    'unweighted_available_min': 'service-minutes', 'unweighted_downtime_min': 'service-minutes',
    'actions_completed': 'actions', 'actions_not_completed': 'actions',
}

METRIC_UNITS.update({key.replace('_min', '_so_far_min') if key.endswith('_min') else key + '_so_far': unit
                     for key, unit in list(METRIC_UNITS.items())})


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
        episodes = import_module('project.simulation.episode')
    except ImportError:
        return False  # Data-only main remains usable before the simulator merges.
    core = session.core

    episode = None
    root_hash = choice.content_hash
    # <data>/processed/agent_inputs/<split>/<case>.json -> <data>; works for data/ and releases/*/data.
    data_root = (root / choice.key).parents[3]

    def callback(state, plan):
        nonlocal episode
        visible = loader.CaseLoader(data_root / 'processed/agent_inputs').load_case(root / choice.key)
        if digest(visible) != root_hash:
            raise ValueError('Selected source changed before simulation')
        if episode is None:
            truth = evaluator.EvaluatorLoader(data_root / 'evaluation/ground_truth').load(state.scenario_id)
            episode = episodes.IncidentEpisode(visible, truth)
        # Only appended, audited operator reports may rebind the visible input.
        # The engine checks all other fields and never changes its private truth.
        if digest(state.scenario) != episode.visible_hash:
            episode.accept_confirmation(state.scenario)
        result = episode.advance(state.scenario, plan, core.approval, state=state)
        metadata = dict(result.run_metadata)
        metadata.update(metric_units=METRIC_UNITS, integration_scope='event_episode',
                        source_input_hash=root_hash)
        return result.model_copy(update={'run_metadata': metadata})

    def checkpoint():
        if episode is None:
            raise IntegrationNotReady('No incident checkpoint exists')
        return episode.checkpoint()

    session.checkpoint_provider = checkpoint
    attach_simulator(session, callback, LABEL)
    return True
