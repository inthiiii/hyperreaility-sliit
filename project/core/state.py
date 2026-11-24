"""Conservative evidence resolution; no access to evaluation labels or hidden state."""
import hashlib
import json
from collections import defaultdict
from .schemas import EvidenceFact, ScenarioInput, VerifiedState

AUTHORITY = {'authoritative_snapshot', 'confirmed_field_update', 'operator_confirmation', 'simulated_completion'}

def digest(obj) -> str:
    value=obj.model_dump(mode='json',by_alias=True) if hasattr(obj,'model_dump') else obj
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def build_verified_state(scenario:ScenarioInput, facts:list[EvidenceFact], confirmations:list[EvidenceFact]|None=None,
                         state_version:int=1) -> VerifiedState:
    observations=scenario.observed_state.model_copy(deep=True)
    reports={r.report_id:r for r in scenario.reports}
    grouped=defaultdict(list)
    all_facts=[*facts,*(confirmations or [])]
    # Independently retain recognized authoritative fixture reports, even if an agent
    # omits one side of a conflict. This is a narrow parser, not semantic verification.
    from project.agents.extraction import template_facts
    recognized=template_facts(scenario)
    by_report={f.evidence_ids[0]:f for f in recognized}
    for fact in all_facts:
        for rid in fact.evidence_ids:
            expected=by_report.get(rid)
            if expected and (fact.target_type,fact.target_id,fact.attribute,fact.value)!=(expected.target_type,expected.target_id,expected.attribute,expected.value):
                raise ValueError('Fact contradicts the cited fixture report')
    existing={(rid,f.target_type,f.target_id,f.attribute) for f in all_facts for rid in f.evidence_ids}
    all_facts.extend(f for f in recognized if reports[f.evidence_ids[0]].source_type in AUTHORITY
                     and (f.evidence_ids[0],f.target_type,f.target_id,f.attribute) not in existing)
    confirm_ids={id(f) for f in (confirmations or [])}
    for fact in all_facts:
        if any(rid not in reports for rid in fact.evidence_ids):
            raise ValueError('Fact cites nonexistent report')
        if fact.observed_at_min is not None and fact.observed_at_min!=max(reports[r].observed_at_min for r in fact.evidence_ids):
            raise ValueError('Fact observation time disagrees with cited reports')
        if fact.received_at_min is not None and fact.received_at_min!=max(reports[r].received_at_min for r in fact.evidence_ids):
            raise ValueError('Fact receipt time disagrees with cited reports')
        typ,target,attr=fact.target_type,fact.target_id,fact.attribute
        valid=(typ=='site' and target in observations.sites and attr in ('equipment_ok','grid_power_ok')) or (typ=='link' and target in observations.links and attr=='backhaul_ok') or (typ=='road' and target in observations.roads and attr=='open')
        if not valid: raise ValueError('Fact has invalid target or attribute')
        if id(fact) in confirm_ids and not all(reports[r].source_type=='operator_confirmation' for r in fact.evidence_ids):
            raise ValueError('Confirmation requires recorded operator evidence')
        grouped[typ,target,attr].append(fact)
    for (typ,target,attr),group in grouped.items():
        if typ=='site': original=getattr(observations.sites[target],attr)
        else: original=getattr(observations,typ+'s' if typ=='link' else 'roads')[target]
        confirmed=[f for f in group if all(reports[r].source_type=='operator_confirmation' for r in f.evidence_ids)]
        observed_completions=[f for f in group if all(reports[r].source_type=='simulated_completion' for r in f.evidence_ids)]
        # Completed approved work establishes a new physical state; this is not
        # a recency-based resolution of contradictory field reports.
        latest_completion=max((reports[r].observed_at_min for f in observed_completions for r in f.evidence_ids), default=-1)
        completed=[f for f in observed_completions if max(reports[r].observed_at_min for r in f.evidence_ids)==latest_completion]
        candidates=confirmed or completed or [f for f in group if all(reports[r].source_type in AUTHORITY for r in f.evidence_ids)]
        values={f.value for f in candidates if f.value is not None}
        conflict=any(f.status=='conflict' for f in candidates) or len(values)>1
        if original is not None and not confirmed and values and original not in values: conflict=True
        if conflict: value=None
        elif candidates and all(f.status=='verified' and f.value is not None for f in candidates): value=next(iter(values))
        else: value=original
        if typ=='site': setattr(observations.sites[target],attr,value)
        elif typ=='link': observations.links[target]=value
        else: observations.roads[target]=value
    unknown=[]
    for sid,v in observations.sites.items():
        for field in ['equipment_ok','grid_power_ok']:
            if getattr(v,field) is None: unknown.append(f'site:{sid}:{field}')
    for typ,values in [('link',observations.links),('road',observations.roads)]:
        unknown.extend(f'{typ}:{key}' for key,value in values.items() if value is None)
    return VerifiedState(scenario_id=scenario.scenario_id,state_version=state_version,source_hash=digest(scenario),
                         scenario=scenario.model_copy(deep=True),resolved_observations=observations,
                         facts=all_facts,unresolved_facts=sorted(unknown))
