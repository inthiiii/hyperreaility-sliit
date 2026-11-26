"""Role-aware to-do badges for the sidebar. Pure reads of the session; never acts."""
from __future__ import annotations

from project.auth import can
from project.ui.agent_view import inbox
from project.ui.review_service import active_approval


def notifications(session, choice, user):
    """[(page, message)] for things this user can act on now."""
    if choice is None or user is None:
        return []
    out = []
    result = session.core.current
    matching = result is not None and result.state.source_hash == choice.content_hash
    current = matching and result.plan is not None
    approved = current and bool(active_approval(session, choice))
    decision = session.last_decision
    rejected = current and decision is not None and decision.approval.plan_id == result.plan.plan_id \
        and decision.approval.decision == 'reject'
    sim = session.simulation_result
    paused = sim is not None and bool(sim.run_metadata.get('replan_required'))
    if current and result.status == 'awaiting_approval' and not approved and not rejected:
        if can(user, 'approve_plan'):
            out.append(('Planning', 'A plan is waiting for your approval'))
        elif can(user, 'generate_plan'):
            out.append(('Planning', 'Plan sent: waiting for a Restoration Manager'))
    if rejected and can(user, 'generate_plan'):
        out.append(('Planning', 'Plan rejected: revise and generate again'))
    if approved and sim is None and can(user, 'simulate'):
        out.append(('Planning', 'Approved plan ready to simulate'))
    if paused and can(user, 'continue_incident'):
        out.append(('Planning', 'Incident event: accept the update and replan'))
    if matching and not approved and can(user, 'confirm_fact'):
        questions = len(inbox(result)['questions'])
        if questions:
            out.append(('Planning', f'{questions} agent question{"s" if questions > 1 else ""} to answer'))
    if approved and can(user, 'confirm_fact') and not can(user, 'generate_plan'):
        jobs = len(result.plan.actions)
        out.append(('Field work', f'{jobs} job{"s" if jobs != 1 else ""} assigned in the approved plan'))
    return out


def badge_counts(items):
    counts = {}
    for page, _ in items:
        counts[page] = counts.get(page, 0) + 1
    return counts
