"""Shared visible context and conservative, evidence-linked agent decisions."""
from typing import Literal
from pydantic import Field
from project.core.schemas import Contract
from project.core.state import digest
from project.agents.context import action_catalog,observations_view

PROTOCOL_VERSION = 'matched-workflow-v13'
OUTPUT_LIMITS={'investigate':700,'resources':450,'priorities':450,'review':500}
STAGES = ('investigate', 'resources', 'priorities', 'review')
TASKS = {
    'investigate': 'Extract each report claim separately with its exact value, evidence ID and timestamps. Never merge opposing claims into null. Only authoritative_snapshot, confirmed_field_update, operator_confirmation and simulated_completion support verified facts; other sources stay unverified. Use equipment/grid/backhaul/road attributes only. Permit restrictions belong to resource requests. Preserve missing facts; do not invent or infer verification.',
    'resources': 'Inspect crews, routes, windows and generators. Keep finding under 600 characters. Confirmed missing permits or operational holds require typed defer_action requests for affected known IDs, with evidence and reason. Do not leave holds only in prose. Known restrictions are not missing evidence; prerequisites alone do not justify holds. Equipment repair never restores grid power.',
    'priorities': 'Apply approved service weights and the supplied objective; never change policy. Keep finding under 600 characters. Use typed evidence-linked holds only when necessary; known weights and trade-offs do not require clarification.',
    'review': 'Check evidence, policy, encoded validation and holds. service_forecast includes unaffected and repaired services: use its per-service accounting, not only generator-site availability. Temporary power does not imply all weighted minutes come from that generator. Use at most three findings of 240 characters each. Approval means ready for human review, not execution or measured restoration. Unmet faults alone are not violations. Do not demand simulator results before human approval. Revise with a concrete evidence correction or typed defer_action request; new holds always require a new validated candidate and fresh review. An approve response may acknowledge existing holds only. Use arithmetic_checks: work_start already includes travel or waiting; end = work_start + duration. Never add travel twice. Escalate genuine uncertainty or unsupported constraints.',
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
            'objective':'Maximize approved weighted service-minutes; then fewer actions and earlier completion.',
            'availability':'Working equipment AND (grid OR unexpired generator) AND working, powered upstream path to core.',
            'repair_semantics':'Equipment repair fixes equipment only; link repair fixes its backhaul only; generator gives temporary power only.',
            'approval':'Agent review -> human approval -> independent simulation. Predictions are not measurements.',
            'snapshot':'Resolved state is complete supplied data. Encoding default true preserves known input values, not guessed health. Unknowns are explicit. Positive snapshot facts need no duplicate narrative report.',
            'authority':'Unverified messages are not equal to authoritative snapshots. Neither recency nor agent agreement verifies facts.',
            'uncertainty':'Missing critical facts or policy block. Known closed roads and unmet needs alone do not.',
            'timing':'Travel starts at departure; work_start follows travel/waiting; work_end = work_start + action duration.',
            'tables':'Action CSV uses listed headers and integer spec_index into specs. State encoding sparse_default_true covers ALL supplied site/link/road IDs: every attribute is true except explicit *_false and *_unknown lists. Unknown is null, never true.'},
        'incident': [scenario.scenario_id, scenario.current_time_min, scenario.horizon_min, scenario.core_id, scenario.depot_id],
        'site_ids': [s.site_id for s in scenario.sites],
        'links_parent_child': [[l.link_id,l.parent,l.child] for l in scenario.links],
        'roads_from_to_minutes': [[r.road_id,r.origin,r.to,r.travel_minutes] for r in scenario.roads],
        'services_site_critical_weight_policy': [[s.service_id,s.site_id,s.critical,s.weight,s.policy_evidence_id] for s in scenario.services],
        'crews_location_from_until_skills': [[c.crew_id,c.location,c.available_from_min,c.available_until_min,c.skills] for c in scenario.crews],
        'generators_location_available_autonomy_deployments_setup': [[g.generator_id,g.location,g.available,g.autonomy_minutes,g.max_deployments,g.deployment_minutes] for g in scenario.generators],
        'action_catalog':action_catalog(scenario.action_options),
        'observations':observations_view(scenario.observed_state),
        'active_generators': [g.model_dump() for g in scenario.active_generators],
        'reports': [r.model_dump() for r in scenario.reports],
        'policy': scenario.policy.model_dump(),
    }


def protocol_manifest():
    return {'version':PROTOCOL_VERSION, 'stages':list(STAGES),
            'tasks_sha256':digest(TASKS), 'visible_context':'identical operational fields; no evaluator truth',
            'tools':['conservative evidence resolver','CP-SAT/greedy scheduler','independent schedule validator'],
            'agent_requests':['evidence-linked conservative defer_action'],
            'weights':'human-approved; never model-edited', 'max_revision_rounds':3,'stage_output_limits':OUTPUT_LIMITS,
            'single':'one agent identity across all four stages',
            'multi':'four distinct role contexts exchanging structured findings',
            'budget_policy':'same whole-incident caps; actual utilization may differ',
            'interpretation':'controlled workflow comparison, not proof that agent count alone causes improvement'}
