"""Static recovery scheduling with exact five-minute service availability on a tree.

Predictions use verified observations only. These are not simulator results.
Future events, partial work and generator redeployment require a later contract.
"""
from __future__ import annotations
from math import ceil
from uuid import uuid4
import networkx as nx
from ortools.sat.python import cp_model
from .schemas import Plan, ScheduledAction, VerifiedState
from .state import digest
from .validator import road_graph, action_needed, validate

SLOT=5

def _route(graph,origin,option,generators):
    stops=[origin]
    if option.kind=='generator_deploy': stops.append(generators[option.generator_id].location)
    stops.append(option.location)
    route=[origin];minutes=0
    for a,b in zip(stops,stops[1:]):
        path=nx.shortest_path(graph,a,b,weight='weight')
        minutes+=nx.path_weight(graph,path,'weight') if len(path)>1 else 0
        route.extend(path[1:])
    return route,minutes

def _eligible(state):
    gens={g.generator_id:g for g in state.scenario.generators}
    return [o for o in state.scenario.action_options if action_needed(state,o) and
            (o.kind!='generator_deploy' or gens[o.generator_id].available)]

def _finish(state,actions,config):
    chosen={a.action_id for a in actions}
    unmet=[f'Unresolved evidence: {x}' for x in state.unresolved_facts]
    unmet.extend(f'Grid outage at {sid}; any generator recovery is temporary and requires simulator evaluation' for sid,obs in state.resolved_observations.sites.items() if obs.grid_power_ok is False)
    unmet.extend(f'Unscheduled fault option: {o.action_id}' for o in _eligible(state) if o.action_id not in chosen)
    plan=Plan(plan_id=str(uuid4()),scenario_id=state.scenario_id,state_version=state.state_version,
              state_hash=digest(state),actions=actions,unmet_needs=unmet,
              evidence_ids=sorted({state.scenario.policy.evidence_id}|{rid for f in state.facts for rid in f.evidence_ids}),
              planner_config=config,
              explanation='Prediction from verified evidence; unknown assets are conservatively unavailable. Unmet needs may remain.')
    result=validate(plan,state)
    if not result.valid: raise ValueError('Planner emitted invalid schedule: '+str(result.model_dump()))
    return plan

def greedy_plan(state:VerifiedState) -> Plan:
    """Feasible earliest-finish heuristic. Not claimed to optimize downtime."""
    graph=road_graph(state);s=state.scenario;gens={g.generator_id:g for g in s.generators}
    ready={c.crew_id:max(s.current_time_min,c.available_from_min) for c in s.crews}
    locations={c.crew_id:c.location for c in s.crews};actions=[];used=False
    pending=_eligible(state)
    while pending:
        choices=[]
        for o in pending:
            if o.kind=='generator_deploy' and used: continue
            for crew in s.crews:
                if o.required_skill not in crew.skills: continue
                try:route,travel=_route(graph,locations[crew.crew_id],o,gens)
                except (nx.NetworkXNoPath,nx.NodeNotFound):continue
                departure=ready[crew.crew_id];start=departure+travel;end=start+o.duration_minutes
                if end<=min(s.horizon_min,crew.available_until_min): choices.append((end,o.action_id,crew.crew_id,o,route,departure,start))
        if not choices:break
        end,_,cid,o,route,departure,start=min(choices,key=lambda x:x[:3])
        actions.append(ScheduledAction(action_id=o.action_id,kind=o.kind,target_id=o.target_id,crew_id=cid,
                                      generator_id=o.generator_id,departure_min=departure,travel_route=route,
                                      work_start_min=start,work_end_min=end))
        ready[cid]=end;locations[cid]=o.location
        if o.kind=='generator_deploy':used=True
        pending.remove(o)
    return _finish(state,actions,{'algorithm':'greedy_earliest_finish','objective':'heuristic; not downtime optimal'})

def plan(state:VerifiedState, solver_seconds:float=5, seed:int=22) -> Plan:
    if not 0<solver_seconds<=5:raise ValueError('Solver budget must be in (0,5] seconds')
    s=state.scenario;obs=state.resolved_observations;graph=road_graph(state)
    options=_eligible(state);gens={g.generator_id:g for g in s.generators}
    if s.current_time_min%SLOT or s.horizon_min%SLOT or any(g.autonomy_minutes%SLOT for g in s.generators):
        raise ValueError('CP-SAT v0.1 current time, horizon and generator autonomy must align to five-minute slots')
    if any(o.duration_minutes%SLOT for o in options):raise ValueError('CP-SAT v0.1 work durations must be multiples of five minutes')
    m=cp_model.CpModel();H=s.horizon_min//SLOT;now=ceil(s.current_time_min/SLOT)
    selected={};starts={};ends={};assigned={};arcs={}
    for i,o in enumerate(options):
        selected[i]=m.new_bool_var(f'select_{i}')
        starts[i]=m.new_int_var(now,H,f'start_{i}')
        ends[i]=m.new_int_var(now,H,f'end_{i}')
        m.add(ends[i]==starts[i]+o.duration_minutes//SLOT).only_enforce_if(selected[i])
        m.add(starts[i]==now).only_enforce_if(selected[i].Not())
        m.add(ends[i]==now).only_enforce_if(selected[i].Not())
        ass=[]
        for c in s.crews:
            if o.required_skill not in c.skills:continue
            a=m.new_bool_var(f'crew_{c.crew_id}_{i}');assigned[c.crew_id,i]=a;ass.append(a)
            m.add(starts[i]>=ceil(max(s.current_time_min,c.available_from_min)/SLOT)).only_enforce_if(a)
            m.add(ends[i]<=min(H,c.available_until_min//SLOT)).only_enforce_if(a)
        m.add(sum(ass)==selected[i])
    deployments=[selected[i] for i,o in enumerate(options) if o.kind=='generator_deploy']
    m.add(sum(deployments)<=1)
    # A virtual return arc closes the circuit; returning to depot after final work is not required.
    for c in s.crews:
        nodes=[i for i in range(len(options)) if (c.crew_id,i) in assigned];edges=[]
        empty=m.new_bool_var(f'empty_{c.crew_id}');edges.append((0,0,empty))
        for i in nodes:
            a=assigned[c.crew_id,i];edges.append((i+1,i+1,a.Not()))
            m.add_implication(a,empty.Not())
            for prev in [None,*[j for j in nodes if j!=i]]:
                origin=c.location if prev is None else options[prev].location
                try:_,travel=_route(graph,origin,options[i],gens)
                except (nx.NetworkXNoPath,nx.NodeNotFound):continue
                arc=m.new_bool_var(f'arc_{c.crew_id}_{prev}_{i}')
                edges.append((0 if prev is None else prev+1,i+1,arc));arcs[c.crew_id,prev,i]=arc
                earliest=ceil(max(s.current_time_min,c.available_from_min)/SLOT) if prev is None else ends[prev]
                m.add(starts[i]>=earliest+ceil(travel/SLOT)).only_enforce_if(arc)
            back=m.new_bool_var(f'finish_{c.crew_id}_{i}');edges.append((i+1,0,back))
        m.add_circuit(edges)
    lookup={(o.kind,o.target_id):i for i,o in enumerate(options) if o.kind!='generator_deploy'}
    cache={}
    def conjunction(terms,name):
        b=m.new_bool_var(name)
        if not terms:m.add(b==1)
        else:
            m.add_bool_and(terms).only_enforce_if(b)
            m.add_bool_or([t.Not() for t in terms]+[b])
        return b
    def disjunction(terms,name):
        b=m.new_bool_var(name)
        if not terms:m.add(b==0)
        else:
            m.add_bool_or(terms).only_enforce_if(b)
            for t in terms:m.add_implication(t,b)
        return b
    def completed(i,t):
        key=('done',i,t)
        if key not in cache:
            before=m.new_bool_var(f'before_{i}_{t}')
            m.add(ends[i]<=t).only_enforce_if(before);m.add(ends[i]>t).only_enforce_if(before.Not())
            cache[key]=conjunction([selected[i],before],f'done_{i}_{t}')
        return cache[key]
    def generator_on(sid,t):
        terms=[]
        for i,o in enumerate(options):
            if o.kind!='generator_deploy' or o.target_id!=sid:continue
            active=m.new_bool_var(f'fuel_{i}_{t}')
            # t is in integer five-minute units, while autonomy need not be divisible by five.
            expiry=gens[o.generator_id].autonomy_minutes
            m.add(ends[i]*SLOT+expiry>t*SLOT).only_enforce_if(active)
            m.add(ends[i]*SLOT+expiry<=t*SLOT).only_enforce_if(active.Not())
            terms.append(conjunction([completed(i,t),active],f'on_{i}_{t}'))
        return disjunction(terms,f'powered_{sid}_{t}')
    parent={l.child:l for l in s.links}
    objectives=[]
    for t in range(now,ceil(s.horizon_min/SLOT)):
        status={s.core_id:m.new_constant(1)}
        def available(sid):
            if sid in status:return status[sid]
            node=obs.sites[sid];link=parent[sid];requirements=[]
            for kind,target,initial in [('equipment_repair',sid,node.equipment_ok),('link_repair',link.link_id,obs.links[link.link_id])]:
                if initial is True:requirements.append(m.new_constant(1))
                elif initial is False and (kind,target) in lookup:requirements.append(completed(lookup[kind,target],t))
                else:requirements.append(m.new_constant(0))
            requirements.append(m.new_constant(1) if node.grid_power_ok is True else generator_on(sid,t) if node.grid_power_ok is False else m.new_constant(0))
            requirements.append(available(link.parent))
            status[sid]=conjunction(requirements,f'available_{sid}_{t}')
            return status[sid]
        width=min(SLOT,s.horizon_min-t*SLOT)
        objectives.extend(service.weight*width*available(service.site_id) for service in s.services)
    # Tie break on fewer tasks; cannot outweigh a single weighted minute of availability.
    time_bound=len(options)*H+1
    m.maximize(sum(objectives)*(len(options)+1)*time_bound-sum(selected.values())*time_bound-sum(ends.values()))
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=solver_seconds
    solver.parameters.random_seed=seed;solver.parameters.num_search_workers=1
    result=solver.solve(m);status=solver.status_name(result)
    config={'algorithm':'cp_sat_time_indexed','solver_status':status,'solver_seconds_cap':solver_seconds,
            'seed':seed,'workers':1,'slot_minutes':SLOT,'prediction_only':True,'tie_breakers':['fewer actions','earlier work completion'],
            'limitations':['static rooted tree','unknown assets unavailable','no in-progress work or future-event scheduling']}
    if result not in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        fallback=greedy_plan(state)
        fallback.planner_config={**config,'fallback':'greedy_earliest_finish','fallback_config':fallback.planner_config}
        return fallback
    config['objective_value']=solver.objective_value;config['best_objective_bound']=solver.best_objective_bound
    predicted=solver.value(sum(objectives))
    config['predicted_weighted_available_minutes_remaining']=predicted
    config['predicted_weighted_downtime_remaining']=sum(x.weight for x in s.services)*(s.horizon_min-s.current_time_min)-predicted
    actions=[]
    for c in s.crews:
        prev=None;location=c.location;ready=max(s.current_time_min,c.available_from_min)
        while True:
            nxt=[i for i in range(len(options)) if (c.crew_id,prev,i) in arcs and solver.value(arcs[c.crew_id,prev,i])]
            if not nxt:break
            i=nxt[0];o=options[i];route,_=_route(graph,location,o,gens)
            actions.append(ScheduledAction(action_id=o.action_id,kind=o.kind,target_id=o.target_id,crew_id=c.crew_id,
                generator_id=o.generator_id,departure_min=ready,travel_route=route,
                work_start_min=solver.value(starts[i])*SLOT,work_end_min=solver.value(ends[i])*SLOT))
            location=o.location;ready=solver.value(ends[i])*SLOT;prev=i
    return _finish(state,actions,config)
