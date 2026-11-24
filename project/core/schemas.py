"""Version 0.1 contracts. Agent-visible objects deliberately exclude evaluator truth."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

Kind = Literal['equipment_repair', 'link_repair', 'generator_deploy']

class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True, validate_assignment=True)

class Site(Contract):
    site_id: str = Field(min_length=1)
    label: str
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)
    coordinate_system: Literal['synthetic_local_grid']

class Link(Contract):
    link_id: str
    parent: str
    child: str

class Road(Contract):
    road_id: str
    origin: str = Field(alias='from')
    to: str
    travel_minutes: int = Field(gt=0, strict=True)

class Service(Contract):
    service_id: str
    site_id: str
    label: str
    critical: StrictBool
    weight: int = Field(gt=0, strict=True)
    policy_evidence_id: str

class Crew(Contract):
    crew_id: str
    location: str
    available_from_min: int = Field(ge=0, strict=True)
    available_until_min: int = Field(gt=0, strict=True)
    skills: list[str]

    @model_validator(mode='after')
    def time_window(self):
        if self.available_until_min <= self.available_from_min:
            raise ValueError('Crew window must have positive duration')
        return self

class Generator(Contract):
    generator_id: str
    location: str
    available: StrictBool
    autonomy_minutes: int = Field(gt=0, strict=True)
    deployment_minutes: int = Field(gt=0, strict=True)
    max_deployments: Literal[1] = 1

class SiteState(Contract):
    equipment_ok: StrictBool | None
    grid_power_ok: StrictBool | None

class Observations(Contract):
    sites: dict[str, SiteState]
    links: dict[str, StrictBool | None]
    roads: dict[str, StrictBool | None]

class ActionOption(Contract):
    action_id: str
    kind: Kind
    target_id: str
    location: str
    duration_minutes: int = Field(gt=0, strict=True)
    required_skill: str
    generator_id: str | None = None

class Report(Contract):
    supersedes_report_ids: list[str] = Field(default_factory=list, exclude_if=lambda value: not value)
    report_id: str
    source_type: str
    observed_at_min: int = Field(strict=True)
    received_at_min: int = Field(strict=True)
    text: str = Field(min_length=1)

class Policy(Contract):
    evidence_id: str
    approved_for_simulation: StrictBool
    standard_weight: int = Field(gt=0, strict=True)
    critical_weight: int = Field(gt=0, strict=True)
    evidence_rule: str
    max_generator_deployments_per_scenario: Literal[1] = 1
    on_crew_loss: str

class ActiveGenerator(Contract):
    """Observed running deployment with expected expiry from public resource specification."""
    generator_id: str
    site_id: str
    expires_at_min: int = Field(gt=0, strict=True)

class ScenarioInput(Contract):
    schema_version: Literal['0.1']
    scenario_id: str = Field(min_length=1)
    region_label: str
    current_time_min: int = Field(ge=0, strict=True)
    horizon_min: int = Field(gt=0, strict=True)
    core_id: str
    depot_id: str
    sites: list[Site] = Field(min_length=1)
    links: list[Link]
    roads: list[Road]
    services: list[Service]
    crews: list[Crew]
    generators: list[Generator]
    observed_state: Observations
    active_generators: list[ActiveGenerator] = Field(default_factory=list)
    action_options: list[ActionOption]
    reports: list[Report]
    policy: Policy

    @model_validator(mode='after')
    def integrity(self):
        groups = [(self.sites,'site_id'), (self.links,'link_id'), (self.roads,'road_id'),
                  (self.services,'service_id'), (self.crews,'crew_id'),
                  (self.generators,'generator_id'), (self.action_options,'action_id'),
                  (self.reports,'report_id')]
        for records, attr in groups:
            ids = [getattr(x,attr) for x in records]
            if any(not x.strip() for x in ids) or len(ids)!=len(set(ids)):
                raise ValueError(f'Empty or duplicate {attr}')
        sites = {s.site_id for s in self.sites}
        links = {l.link_id for l in self.links}
        roads = {r.road_id for r in self.roads}
        gens = {g.generator_id:g for g in self.generators}
        places = sites | {self.depot_id}
        if self.core_id in sites or self.depot_id in sites or self.core_id==self.depot_id:
            raise ValueError('Core, depot and sites must be distinct')
        if self.current_time_min >= self.horizon_min:
            raise ValueError('Current time must precede horizon')
        parent = {}
        for link in self.links:
            if link.child not in sites or link.parent not in sites|{self.core_id}:
                raise ValueError('Dangling backhaul endpoint')
            if link.child in parent:
                raise ValueError('Version 0.1 supports one upstream parent per site')
            parent[link.child] = link.parent
        for site in sites:
            seen, cursor = set(), site
            while cursor!=self.core_id:
                if cursor in seen or cursor not in parent:
                    raise ValueError('Cyclic or disconnected backhaul')
                seen.add(cursor); cursor=parent[cursor]
        edges=set()
        for road in self.roads:
            edge=tuple(sorted([road.origin,road.to]))
            if road.origin not in places or road.to not in places or road.origin==road.to or edge in edges:
                raise ValueError('Invalid or duplicate undirected road edge')
            edges.add(edge)
        if any(c.location not in places for c in self.crews) or any(g.location not in places for g in self.generators):
            raise ValueError('Unknown resource location')
        for service in self.services:
            if service.site_id not in sites or service.policy_evidence_id!=self.policy.evidence_id:
                raise ValueError('Invalid service reference or policy evidence')
            expected=self.policy.critical_weight if service.critical else self.policy.standard_weight
            if service.weight!=expected:
                raise ValueError('Service weight disagrees with approved policy')
        obs=self.observed_state
        if set(obs.sites)!=sites or set(obs.links)!=links or set(obs.roads)!=roads:
            raise ValueError('Observations must match all known assets exactly')
        for action in self.action_options:
            if action.location not in sites:
                raise ValueError('Unknown work location')
            if action.kind=='link_repair':
                matches=[l for l in self.links if l.link_id==action.target_id]
                if not matches or matches[0].child!=action.location or action.required_skill!='backhaul' or action.generator_id:
                    raise ValueError('Invalid link repair option')
            else:
                if action.target_id not in sites or action.location!=action.target_id:
                    raise ValueError('Invalid site action reference')
                if action.kind=='equipment_repair' and (action.required_skill!='equipment' or action.generator_id):
                    raise ValueError('Invalid equipment repair option')
                if action.kind=='generator_deploy':
                    gen=gens.get(action.generator_id)
                    if not gen or action.required_skill!='generator' or action.duration_minutes!=gen.deployment_minutes:
                        raise ValueError('Invalid generator deployment option')
        active_ids = set()
        for active in self.active_generators:
            if active.generator_id not in gens or active.site_id not in sites or active.generator_id in active_ids:
                raise ValueError('Invalid or duplicate active generator')
            if gens[active.generator_id].available or active.expires_at_min <= self.current_time_min:
                raise ValueError('Running generator must be unavailable for redeployment and unexpired')
            active_ids.add(active.generator_id)
        earlier_reports = {}
        for report in self.reports:
            if report.supersedes_report_ids:
                if report.source_type != 'operator_confirmation' or len(set(report.supersedes_report_ids)) != len(report.supersedes_report_ids):
                    raise ValueError('Only explicit operator confirmations can supersede earlier confirmations')
                if any(rid not in earlier_reports or earlier_reports[rid].source_type != 'operator_confirmation'
                       for rid in report.supersedes_report_ids):
                    raise ValueError('Superseded confirmation must be an earlier operator report')
            earlier_reports[report.report_id] = report
            if report.observed_at_min>report.received_at_min or report.received_at_min>self.current_time_min:
                raise ValueError('Report time ordering or future evidence invalid')
        return self

class EvidenceFact(Contract):
    target_type: Literal['site','link','road']
    target_id: str
    attribute: Literal['equipment_ok','grid_power_ok','backhaul_ok','open']
    value: StrictBool | None
    evidence_ids: list[str] = Field(min_length=1)
    observed_at_min: int | None = None
    received_at_min: int | None = None
    status: Literal['verified','unverified','conflict'] = 'unverified'
    reason: str = ''

class VerifiedState(Contract):
    scenario_id: str
    state_version: int = Field(ge=1, strict=True)
    source_hash: str
    scenario: ScenarioInput
    resolved_observations: Observations
    facts: list[EvidenceFact]
    unresolved_facts: list[str]

class ScheduledAction(Contract):
    action_id: str
    kind: Kind
    target_id: str
    crew_id: str
    generator_id: str | None = None
    departure_min: int = Field(ge=0, strict=True)
    travel_route: list[str] = Field(min_length=1)
    work_start_min: int = Field(ge=0, strict=True)
    work_end_min: int = Field(gt=0, strict=True)

class Plan(Contract):
    plan_id: str
    scenario_id: str
    state_version: int = Field(ge=1, strict=True)
    state_hash: str
    actions: list[ScheduledAction]
    unmet_needs: list[str]
    evidence_ids: list[str]
    planner_config: dict
    explanation: str = ''

class Violation(Contract):
    code: str
    action_id: str | None = None
    reason: str

class ValidationResult(Contract):
    valid: StrictBool
    violations: list[Violation]

class Approval(Contract):
    plan_id: str
    plan_hash: str
    state_version: int
    state_hash: str
    decision: Literal['approve','reject']
    operator_id: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=lambda:datetime.now(timezone.utc))

class SimulationResult(Contract):
    """Shared output contract; evaluator implementation belongs to Zahra."""
    scenario_id: str
    plan_id: str
    state_version: int
    trajectory: list[dict]
    completed_actions: list[str]
    unmet_needs: list[str]
    metrics: dict[str, float | int | None]
    run_metadata: dict
