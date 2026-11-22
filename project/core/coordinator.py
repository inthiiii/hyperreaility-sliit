"""Versioned, bounded agent workflow and content-bound operator approval.

Simulation remains a separate evaluator owned by Zahra. No truth loader is imported.
"""
from typing import Literal
from uuid import uuid4
from .schemas import Contract,EvidenceFact,ScenarioInput,Plan,Approval,ValidationResult,VerifiedState
from .state import build_verified_state,digest
from .planner import plan,greedy_plan
from .validator import validate
from project.agents.extraction import template_facts
from project.llm.client import RunBudget,BudgetExceeded

class FactBatch(Contract):facts:list[EvidenceFact]
class Finding(Contract):
    finding:str
    evidence_ids:list[str]
    clarification_required:bool=False
class Review(Contract):
    decision:Literal['approve','revise','escalate']
    findings:list[str]
    evidence_ids:list[str]
    revision_request:str=''

class RunResult(Contract):
    run_id:str
    mode:str
    status:Literal['awaiting_approval','escalated']
    state:VerifiedState
    plan:Plan|None
    validation:ValidationResult|None
    messages:list[dict]
    model_usage:list[dict]
    reasons:list[str]

class Coordinator:
    def __init__(self,adapter=None,budget=None,planner='cp_sat'):
        self.adapter=adapter;self.budget=budget or (adapter.budget if adapter else RunBudget())
        if adapter and adapter.budget is not self.budget:raise ValueError('Adapter and coordinator must share one budget')
        if planner not in ('cp_sat','greedy'):raise ValueError('Unknown planner')
        self.planner=planner

    def run(self,scenario:ScenarioInput,mode='template',state_version=1):
        if mode not in ('template','single','multi'):raise ValueError('Unknown mode')
        self.budget.check_time()
        if mode!='template' and self.adapter is None:raise ValueError('Hosted adapter required; no silent offline fallback')
        if self.budget.calls or self.budget.records:raise ValueError('Use a fresh coordinator/budget for each run')
        messages=[];reasons=[];state=build_verified_state(scenario,[],state_version=state_version)
        candidate=None;validation=None
        reports=[r.model_dump() for r in scenario.reports]
        def message(sender,recipient,content):
            messages.append({'sender':sender,'recipient':recipient,'incident_id':scenario.scenario_id,
                             'state_version':state_version,'finding':content})
        def invoke(role,payload,model):
            self.budget.check_time()
            result=self.adapter.complete(role,payload,model)
            evidence=set(result.evidence_ids) if hasattr(result,'evidence_ids') else {rid for f in result.facts for rid in f.evidence_ids}
            allowed={r.report_id for r in scenario.reports}|{scenario.policy.evidence_id}
            if not evidence<=allowed:raise ValueError('Agent cited nonexistent evidence')
            message(role,'coordinator',result.model_dump())
            return result
        try:
            if mode=='template':
                facts=template_facts(scenario);message('template_baseline','coordinator',{'facts':[f.model_dump() for f in facts],'not_llm':True})
            else:
                facts=invoke('network_investigator' if mode=='multi' else 'single_agent',{'reports':reports,'site_ids':[s.site_id for s in scenario.sites],
                     'link_ids':[l.link_id for l in scenario.links],'road_ids':[r.road_id for r in scenario.roads]},FactBatch).facts
            state=build_verified_state(scenario,facts,state_version=state_version)
            if state.unresolved_facts:
                reasons.extend(state.unresolved_facts)
            if mode=='multi' and not reasons:
                resource=invoke('field_resource_planner',{'evidence':reports,'observations':state.resolved_observations.model_dump(),
                   'crews':[c.model_dump() for c in scenario.crews],'generators':[g.model_dump() for g in scenario.generators],
                   'roads':[r.model_dump(by_alias=True) for r in scenario.roads]},Finding)
                priority=invoke('service_priority_assessor',{'services':[s.model_dump() for s in scenario.services],
                   'policy':scenario.policy.model_dump(),'resource_finding':resource.model_dump(),'evidence':reports},Finding)
                if resource.clarification_required or priority.clarification_required:
                    reasons.append('Specialist requires operator clarification')
            if not reasons:
                for revision in range(4):
                    self.budget.check_time()
                    candidate=greedy_plan(state) if self.planner=='greedy' else plan(state,solver_seconds=min(5,self.budget.remaining_seconds()))
                    validation=validate(candidate,state);message('deterministic_scheduler','coordinator',candidate.model_dump())
                    self.budget.check_time()
                    if not validation.valid:
                        reasons.append('Independent validation failed');break
                    if mode=='template':break
                    review=invoke('plan_reviewer' if mode=='multi' else 'single_agent',{'plan':candidate.model_dump(),'validation':validation.model_dump(),
                       'agent_findings':messages[:],'reports':reports,
                       'tool_state':{'observations':state.resolved_observations.model_dump(),
                           'crews':[c.model_dump() for c in scenario.crews],'generators':[g.model_dump() for g in scenario.generators],
                           'roads':[r.model_dump(by_alias=True) for r in scenario.roads],
                           'links':[l.model_dump() for l in scenario.links],'services':[s.model_dump() for s in scenario.services],
                           'policy':scenario.policy.model_dump()}},Review)
                    if review.decision=='approve':break
                    if review.decision=='escalate' or revision==3:
                        reasons.extend(review.findings or ['Review did not approve within revision budget']);break
                    if not review.revision_request:
                        reasons.append('Reviewer requested revision without a concrete request');break
                    revised=invoke('network_investigator' if mode=='multi' else 'single_agent',{'reports':reports,'revision_request':review.revision_request,
                       'previous_facts':[f.model_dump() for f in state.facts]},FactBatch)
                    state_version+=1
                    state=build_verified_state(scenario,revised.facts,state_version=state_version)
                    if state.unresolved_facts:
                        reasons.extend(state.unresolved_facts);break
                self.budget.check_time()
        except Exception as error:
            reasons.append(f'{type(error).__name__}: workflow stopped; inspect structured usage and evidence')
            candidate=None;validation=None
        return RunResult(run_id=str(uuid4()),mode=mode,status='escalated' if reasons else 'awaiting_approval',
                         state=state,plan=candidate,validation=validation,messages=messages,
                         model_usage=list(self.budget.records),reasons=reasons)

def approve(plan_id:str,state_version:int,decision:str,*,plan:Plan,state:VerifiedState,operator_id:str) -> Approval:
    if (plan_id,state_version)!=(plan.plan_id,state.state_version):raise ValueError('Stale plan or state')
    if not validate(plan,state).valid:raise ValueError('Cannot approve an invalid plan')
    return Approval(plan_id=plan_id,plan_hash=digest(plan),state_version=state_version,state_hash=digest(state),
                    decision=decision,operator_id=operator_id)

def check_approval(approval:Approval,plan:Plan,state:VerifiedState):
    if approval.decision!='approve' or (approval.plan_id,approval.state_version,approval.plan_hash,approval.state_hash)!=(plan.plan_id,state.state_version,digest(plan),digest(state)):
        raise ValueError('Approval missing, rejected or invalidated by a material change')
    if not validate(plan,state).valid:raise ValueError('Approved plan is no longer valid')
