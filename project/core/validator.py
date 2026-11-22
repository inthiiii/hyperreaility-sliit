"""Recompute physical feasibility from emitted actions, independently of the solver."""
from collections import defaultdict
import networkx as nx
from .schemas import Plan, VerifiedState, ValidationResult, Violation
from .state import digest

def road_graph(state):
    graph=nx.Graph()
    graph.add_nodes_from([state.scenario.depot_id,*[s.site_id for s in state.scenario.sites]])
    for road in state.scenario.roads:
        if state.resolved_observations.roads[road.road_id] is True:
            graph.add_edge(road.origin,road.to,weight=road.travel_minutes)
    return graph

def action_needed(state,option):
    obs=state.resolved_observations
    if option.kind=='equipment_repair': return obs.sites[option.target_id].equipment_ok is False
    if option.kind=='link_repair': return obs.links[option.target_id] is False
    return obs.sites[option.target_id].grid_power_ok is False

def validate(plan:Plan,state:VerifiedState) -> ValidationResult:
    errors=[]
    def fail(code,reason,action=None): errors.append(Violation(code=code,reason=reason,action_id=action))
    if (plan.scenario_id,plan.state_version,plan.state_hash)!=(state.scenario_id,state.state_version,digest(state)):
        fail('STALE_STATE','Plan does not match current state and content hash')
    s=state.scenario
    if not s.policy.approved_for_simulation: fail('POLICY','Service policy is not approved')
    options={o.action_id:o for o in s.action_options};crews={c.crew_id:c for c in s.crews}
    gens={g.generator_id:g for g in s.generators};graph=road_graph(state)
    seen=set();used_gen=set();bycrew=defaultdict(list)
    reportids={r.report_id for r in s.reports}|{s.policy.evidence_id}
    if not set(plan.evidence_ids)<=reportids: fail('EVIDENCE','Plan cites unknown evidence')
    for a in plan.actions:
        if a.action_id in seen: fail('DUPLICATE','Action assigned more than once',a.action_id)
        seen.add(a.action_id)
        o=options.get(a.action_id);c=crews.get(a.crew_id)
        if not o or not c:
            fail('REFERENCE','Unknown action or crew',a.action_id);continue
        if (a.kind,a.target_id,a.generator_id)!=(o.kind,o.target_id,o.generator_id):
            fail('ACTION_MISMATCH','Action disagrees with catalogue',a.action_id)
        if o.required_skill not in c.skills: fail('SKILL','Crew lacks required skill',a.action_id)
        if not action_needed(state,o): fail('UNVERIFIED_NEED','Fault is unknown or action is unnecessary',a.action_id)
        if a.work_end_min-a.work_start_min!=o.duration_minutes: fail('DURATION','Incorrect work duration',a.action_id)
        if not max(s.current_time_min,c.available_from_min)<=a.departure_min<=a.work_start_min<a.work_end_min<=min(s.horizon_min,c.available_until_min):
            fail('TIME_WINDOW','Action timing violates current time, horizon or crew availability',a.action_id)
        if o.kind=='generator_deploy':
            gen=gens.get(a.generator_id)
            if not gen or not gen.available: fail('GENERATOR_UNAVAILABLE','Generator unavailable',a.action_id)
            if a.generator_id in used_gen: fail('GENERATOR_REUSE','Generator already deployed',a.action_id)
            used_gen.add(a.generator_id)
            if gen and gen.location not in a.travel_route: fail('GENERATOR_TRANSPORT','Route omits generator pickup location',a.action_id)
        bycrew[c.crew_id].append(a)
    if len(used_gen)>s.policy.max_generator_deployments_per_scenario: fail('GENERATOR_LIMIT','Too many deployments')
    for cid,actions in bycrew.items():
        c=crews[cid];location=c.location;ready=max(s.current_time_min,c.available_from_min)
        for a in sorted(actions,key=lambda a:(a.departure_min,a.work_start_min,a.action_id)):
            o=options[a.action_id]
            if a.departure_min<ready: fail('CREW_OVERLAP','Travel/work overlaps prior work',a.action_id)
            if a.travel_route[0]!=location or a.travel_route[-1]!=o.location:
                fail('ROUTE_ENDPOINT','Route does not join current location and work site',a.action_id)
            duration=0
            for p,q in zip(a.travel_route,a.travel_route[1:]):
                if not graph.has_edge(p,q): fail('ROUTE_CLOSED','Route uses missing, closed or unknown road',a.action_id)
                else: duration+=graph[p][q]['weight']
            if a.work_start_min<a.departure_min+duration: fail('TRAVEL_TIME','Work starts before arrival',a.action_id)
            ready=a.work_end_min;location=o.location
    return ValidationResult(valid=not errors,violations=errors)
