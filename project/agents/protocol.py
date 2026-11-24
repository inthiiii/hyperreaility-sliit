"""Shared visible context and conservative, evidence-linked agent decisions."""
from typing import Literal
from pydantic import Field
from project.core.schemas import Contract
from project.core.state import digest

PROTOCOL_VERSION = 'matched-workflow-v4'
STAGES = ('investigate', 'resources', 'priorities', 'review')
TASKS = {
    'investigate': ('Extract one atomic fact per report claim, keeping the exact reported value, evidence ID and timestamps. '
                    'Do not merge contradictory reports into a null fact with both evidence IDs: retain their individual claims and let the resolver mark the conflict. '
                    'For authoritative_snapshot, confirmed_field_update, operator_confirmation or simulated_completion use verified only for a supported explicit claim; '
                    'other sources remain unverified even if you believe them. Distinguish equipment_ok from grid_power_ok. '
                    'Use only the supported equipment/grid/backhaul/road attributes. A report outside these attributes, such as a permit restriction, belongs to resource findings, not an invented fact attribute. '
                    'Do not infer verification from agent agreement or invent missing observations.'),
    'resources': 'Inspect crew skills/windows, routes, generators and action dependencies. Equipment repair fixes equipment only, never grid power. A grid outage alone does not justify equipment repair. Return findings and, only with evidence and a concrete reason, conservative defer_action requests. A confirmed report of an unissued site access or generator-placement permit is an operational restriction: put the affected known action IDs into requests with kind defer_action, evidence_ids and reason. A restriction with an explicit known status does not require asking what that status is. Do not leave an actionable hold only in prose. Do not invent constraints or require a hold merely because a repair has prerequisites.',
    'priorities': 'Assess service trade-offs under the supplied approved policy. The objective and approved weights already define the trade-off; do not request operator clarification merely to choose between services with known weights. Preserve every service weight. Return findings and only evidence-linked conservative defer_action requests when necessary.',
    'review': ('Challenge the candidate, evidence and applied holds for readiness for separate human approval and subsequent independent simulation. '
               'Approve means ready for human review, never execution or proven restoration. The independent evaluator runs only AFTER approval; '
               'do not require hidden truth, future events or simulator results before approval. Treat all objective values as predictions. '
               'Check known encoded violations, unresolved critical evidence, policy consistency and deferral compliance. '
               'Limited resources and the fewer-actions tie-break can intentionally leave faults unscheduled; their presence alone is not a violation. '
               'Record such limits in findings. Revise for a concrete evidence correction or supported scheduling request, not merely to repair every fault. '
               'If decision is revise, revision_request must be nonempty and concrete; equipment repair cannot fix a grid outage. '
               'For any actionable scheduling deferral populate requests with kind defer_action, action_ids, evidence_ids and reason; prose alone is not executable. '
               'A scheduling deferral must use a typed defer_action request with known action/evidence IDs and a reason. '
               'Escalate actual safety uncertainty or required unsupported constraints; do not silently approve them.'),
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
        'decision_contract': {
            'objective':'Maximize weighted available service-minutes using approved service weights; tie-break on fewer actions, then earlier completion.',
            'service_available_if':'Equipment works AND grid or unexpired generator power exists AND all upstream backhaul links and powered working ancestor sites connect to the core.',
            'equipment_repair':'Repairs equipment only. It does not restore grid power. Do not select it solely because grid_power_ok is false.',
            'link_repair':'Repairs the specified failed backhaul link only. It cannot restore grid power.',
            'generator_deploy':'Temporary power after setup, limited by public autonomy and one deployment; does not repair equipment/backhaul.',
            'approval_boundary':'Agent approve means ready for human review. Human approval precedes independent simulation, which measures physical restoration.',
            'uncertainty':'Escalate unresolved critical evidence or missing policy; known approved weights and intentional unmet needs do not alone require clarification.'},
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
