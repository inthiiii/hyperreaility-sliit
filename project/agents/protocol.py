"""Shared visible context and conservative, evidence-linked agent decisions."""
from typing import Literal
from pydantic import Field
from project.core.schemas import Contract
from project.core.state import digest

PROTOCOL_VERSION = 'matched-workflow-v1'
STAGES = ('investigate', 'resources', 'priorities', 'review')
TASKS = {
    'investigate': 'Extract report-supported facts with exact evidence IDs and times. Preserve unknowns and conflicts. Do not infer verification from agent agreement.',
    'resources': 'Inspect crew skills/windows, routes, generators and action dependencies. Return findings and, only with evidence and a concrete reason, conservative defer_action requests. Do not invent constraints or require a hold merely because a repair has prerequisites.',
    'priorities': 'Assess service trade-offs under the supplied approved policy. Preserve every service weight. Return findings and only evidence-linked conservative defer_action requests when necessary.',
    'review': 'Challenge the candidate and its applied holds using the shared tools. Approve only a validated candidate; request concrete evidence/schedule revision or escalate. Never approve execution.',
}


class DecisionRequest(Contract):
    kind: Literal['defer_action']
    action_ids: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=500)


def visible_context(scenario):
    """Same operational information for both modes; no hidden evaluator fields.

    Tabular encodings reduce framing cost without withholding topology, state,
    action/resource specifications, approved policy or original report text.
    """
    return {
        'incident': [scenario.scenario_id, scenario.current_time_min, scenario.horizon_min, scenario.core_id, scenario.depot_id],
        'site_ids': [s.site_id for s in scenario.sites],
        'links_parent_child': [[l.link_id,l.parent,l.child] for l in scenario.links],
        'roads_from_to_minutes': [[r.road_id,r.origin,r.to,r.travel_minutes] for r in scenario.roads],
        'services_site_critical_weight_policy': [[s.service_id,s.site_id,s.critical,s.weight,s.policy_evidence_id] for s in scenario.services],
        'crews_location_from_until_skills': [[c.crew_id,c.location,c.available_from_min,c.available_until_min,c.skills] for c in scenario.crews],
        'generators_location_available_autonomy_deployments_setup': [[g.generator_id,g.location,g.available,g.autonomy_minutes,g.max_deployments,g.deployment_minutes] for g in scenario.generators],
        'actions_kind_target_location_duration_skill_generator': [[a.action_id,a.kind,a.target_id,a.location,a.duration_minutes,a.required_skill,a.generator_id] for a in scenario.action_options],
        'observations': scenario.observed_state.model_dump(),
        'active_generators': [g.model_dump() for g in scenario.active_generators],
        'reports': [r.model_dump() for r in scenario.reports],
        'policy': scenario.policy.model_dump(),
    }


def protocol_manifest():
    return {'version':PROTOCOL_VERSION, 'stages':list(STAGES),
            'tasks_sha256':digest(TASKS), 'visible_context':'identical operational fields; no evaluator truth',
            'tools':['conservative evidence resolver','CP-SAT/greedy scheduler','independent schedule validator'],
            'agent_requests':['evidence-linked conservative defer_action'],
            'weights':'human-approved; never model-edited', 'max_revision_rounds':3,
            'single':'one agent identity across all four stages',
            'multi':'four distinct role contexts exchanging structured findings',
            'budget_policy':'same whole-incident caps; actual utilization may differ',
            'interpretation':'controlled workflow comparison, not proof that agent count alone causes improvement'}
