"""Accept only the safe visible checkpoint from a successfully recorded episode."""
from project.auth import require
from project.core.schemas import ScenarioInput
from project.core.state import digest
from project.ui.catalog import ScenarioChoice
from project.ui.outcome_data import current_outcome
from project.ui.planning_service import begin_new_attempt
from project.ui.review_service import ReviewBlocked, ensure_current_source


def accept_checkpoint(session, choice, root, *, user=None):
    if user is not None:
        require(user, 'continue_incident')
    result, issue = current_outcome(session)
    if issue or result is None or not result.run_metadata.get('replan_required'):
        raise ReviewBlocked('A matching recorded paused episode is required')
    ensure_current_source(session, choice, root)
    if not callable(session.checkpoint_provider):
        raise ReviewBlocked('The live incident checkpoint is unavailable; historical records cannot resume it')
    checkpoint = ScenarioInput.model_validate(session.checkpoint_provider())
    if (checkpoint.scenario_id != choice.scenario.scenario_id or
            checkpoint.current_time_min <= choice.scenario.current_time_min or
            checkpoint.current_time_min >= checkpoint.horizon_min or
            checkpoint.current_time_min != result.run_metadata.get('observed_until_min')):
        raise ReviewBlocked('Checkpoint identity/time does not match the recorded episode')
    selected = ScenarioChoice(choice.key, 'incident_checkpoint', checkpoint, digest(checkpoint))
    begin_new_attempt(session)  # Monotonic CoreSession state versions and old audit history survive.
    session.continuation_context = {'committed_actions': result.run_metadata.get('committed_actions', [])}
    session.confirmation_choice = None
    session.continuation_choice = selected
    session.scenario_hash = selected.content_hash
    return selected
