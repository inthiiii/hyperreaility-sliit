"""Human decisions on agent priority proposals.

A proposal never changes the approved policy for the running incident: the
simulator scores against the approved policy. Accepting records a signed
request for the policy owner; rejecting records the reason. Both are audited.
"""
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from project.auth import require
from project.ui.local_records import save_record


def proposal_key(result, index):
    return f'{result.run_id}:{index}'


def record_priority_decision(session, result, index, decision, note, root, *, user):
    require(user, 'decide_priority')
    if decision not in ('accept', 'reject'):
        raise ValueError('Choose accept or reject')
    proposals = (result.metadata or {}).get('priority_proposals', [])
    if not 0 <= index < len(proposals):
        raise ValueError('Unknown proposal')
    key = proposal_key(result, index)
    if key in session.priority_decisions:
        return 'duplicate'
    record = {'decision_id': str(uuid4()), 'run_id': result.run_id, 'scenario_id': result.state.scenario_id,
              'proposal': proposals[index], 'decision': decision, 'note': (note or '').strip()[:1000],
              'decided_by': user.label, 'username': user.username, 'role': user.role,
              'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
              'effect': ('Recorded as a policy change request for the policy owner; the approved policy for this '
                         'incident is unchanged.' if decision == 'accept' else 'Proposal rejected; no change.')}
    save_record(Path(root) / 'results/local_runs/priority_decisions', record['decision_id'], record)
    session.priority_decisions[key] = record
    return decision
