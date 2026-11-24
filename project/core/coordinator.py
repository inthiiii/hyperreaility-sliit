"""Versioned, bounded agent workflow and content-bound operator approval.

Simulation remains a separate evaluator owned by Zahra. No truth loader is imported.
"""
from typing import Literal,Annotated
import time
from datetime import datetime, timezone
from pydantic import Field
from uuid import uuid4
from .schemas import Contract,EvidenceFact,ScenarioInput,Plan,Approval,ValidationResult,VerifiedState
from .state import build_verified_state,digest
from .planner import plan,greedy_plan
from .validator import validate
from .forecast import service_forecast
from project.agents.extraction import template_facts
from project.llm.client import RunBudget,BudgetExceeded
from project.evaluation.extraction import extraction_metrics
from project.agents.context import observations_view,plan_view,arithmetic_checks
from project.agents.protocol import DecisionRequest, TASKS, PROTOCOL_VERSION, OUTPUT_LIMITS, visible_context

class FactBatch(Contract):facts:list[EvidenceFact]
class Finding(Contract):
    clarification_required:bool=False
    requests:list[DecisionRequest]=Field(default_factory=list)
    evidence_ids:list[str]
    finding:str=Field(max_length=600)
class Review(Contract):
    decision:Literal['approve','revise','escalate']
    revision_kind:Literal['evidence','schedule']='evidence'
    revision_request:str=''
    requests:list[DecisionRequest]=Field(default_factory=list)
    evidence_ids:list[str]
    findings:list[Annotated[str,Field(max_length=240)]]=Field(max_length=3)

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
    metadata:dict=Field(default_factory=dict)

class Coordinator:
    def __init__(self,adapter=None,budget=None,planner='cp_sat',*,reviewer_enabled=True,feedback_enabled=True,trace_dir=None):
        self.adapter=adapter;self.budget=budget or (adapter.budget if adapter else RunBudget())
        if adapter and adapter.budget is not self.budget:raise ValueError('Adapter and coordinator must share one budget')
        if planner not in ('cp_sat','greedy'):raise ValueError('Unknown planner')
        self.planner=planner
        self.reviewer_enabled=reviewer_enabled;self.feedback_enabled=feedback_enabled
        self.trace_dir=trace_dir;self._used=False

    def run(self,scenario:ScenarioInput,mode='template',state_version=1):
        if mode not in ('template','single','multi'):raise ValueError('Unknown mode')
        if self._used:raise ValueError('Use a fresh coordinator for each run')
        self._used=True
        self.budget.started=time.monotonic()
        started_at=datetime.now(timezone.utc).isoformat()
        self.budget.check_time()
        if mode!='template' and self.adapter is None:raise ValueError('Hosted adapter required; no silent offline fallback')
        if self.budget.calls or self.budget.records:raise ValueError('Use a fresh coordinator/budget for each run')
        messages=[];reasons=[];effects=[];raw_extraction=None;deferred=set();context=visible_context(scenario);state=build_verified_state(scenario,[],state_version=state_version)
        candidate=None;validation=None
        reports=[r.model_dump() for r in scenario.reports]
        recognized=template_facts(scenario)
        recognized_ids={rid for fact in recognized for rid in fact.evidence_ids}
        def message(sender,recipient,content):
            messages.append({'sender':sender,'recipient':recipient,'incident_id':scenario.scenario_id,
                             'state_version':state_version,'finding':content})
        def invoke(role,payload,model,stage):
            self.budget.check_time()
            shared={k:v for k,v in context.items() if k not in ('reports','observations','site_ids')}
            payload={**payload,'reports':reports,'site_ids':context['site_ids'],'stage':stage,'task':TASKS[stage],
                     'shared_context':shared,'context_sha256':digest(context),
                     'state_version':state_version,'resolved_observations':observations_view(state.resolved_observations),
                     'active_deferred_action_ids':sorted(deferred)}
            # Both modes see the same findings. Distinct role identities are the
            # controlled workflow difference, not a hidden information advantage.
            payload['agent_findings']=[{'sender':m['sender'],'state_version':m['state_version'],'finding':m['finding']} for m in messages
                                     if m['sender'] not in ('deterministic_scheduler','coordinator','rejected_agent_output') and 'facts' not in m['finding']][-3:]
            if not self.feedback_enabled:payload['agent_findings']=[]
            allowed={r.report_id for r in scenario.reports}
            if model is not FactBatch:allowed.add(scenario.policy.evidence_id)
            result=self.adapter.complete(role,payload,model,max_output=OUTPUT_LIMITS[stage],evidence_ids=allowed)
            def reject(reason):
                message('rejected_agent_output','audit',{'role':role,'stage':stage,
                        'validation_error':reason,'output':result.model_dump()})
                raise ValueError(reason)
            evidence=set(result.evidence_ids) if hasattr(result,'evidence_ids') else {rid for f in result.facts for rid in f.evidence_ids}
            if not evidence<=allowed:reject('Agent cited nonexistent evidence')
            for request in getattr(result,'requests',[]):
                if not set(request.evidence_ids)<=allowed:reject('Decision request cited nonexistent evidence')
                if not request.reason.strip() or len(set(request.action_ids))!=len(request.action_ids):
                    reject('Invalid decision request')
                if not set(request.action_ids)<={a.action_id for a in scenario.action_options}:
                    reject('Decision request references nonexistent action')
            message(role,'coordinator',result.model_dump())
            return result
        def apply_requests(finding,role):
            nonlocal state,state_version
            for request in finding.requests:
                added=set(request.action_ids)-deferred
                if not added:continue
                if not self.feedback_enabled:
                    reasons.append('Agent requested action deferral; feedback disabled for ablation');return
                deferred.update(added)
                state_version+=1
                state=build_verified_state(scenario,state.facts,state_version=state_version)
                effect={'sender':role,'state_version':state_version,'request':request.model_dump(),
                        'applied_action_ids':sorted(added),'effect':'excluded_from_candidate_schedule',
                        'operational_fact_verified':False}
                effects.append(effect);message('coordinator','deterministic_scheduler',effect)
        def assess_specialists():
            for stage,identity in [('resources','field_resource_planner'),('priorities','service_priority_assessor')]:
                role=identity if mode=='multi' else 'single_agent'
                finding=invoke(role,{},Finding,stage)
                if finding.clarification_required:
                    reasons.append('Specialist requires operator clarification');return
                apply_requests(finding,role)
        try:
            if mode=='template':
                facts=template_facts(scenario);message('template_baseline','coordinator',{'facts':[f.model_dump() for f in facts],'not_llm':True})
            else:
                facts=invoke('network_investigator' if mode=='multi' else 'single_agent',{'reports':reports,'site_ids':[s.site_id for s in scenario.sites],
                     'link_ids':[l.link_id for l in scenario.links],'road_ids':[r.road_id for r in scenario.roads]},FactBatch,'investigate').facts
            if mode!='template':raw_extraction=extraction_metrics(scenario,facts)
            state=build_verified_state(scenario,facts,state_version=state_version)
            if state.unresolved_facts:
                reasons.extend(state.unresolved_facts)
            if mode!='template' and not reasons:assess_specialists()
            if not reasons:
                review_feedback=None
                candidate_dirty=True
                for revision in range(4):
                    self.budget.check_time()
                    if candidate_dirty:
                        candidate=greedy_plan(state,excluded_action_ids=deferred) if self.planner=='greedy' else plan(state,solver_seconds=min(5,self.budget.remaining_seconds()),excluded_action_ids=deferred)
                        validation=validate(candidate,state);message('deterministic_scheduler','coordinator',candidate.model_dump())
                        candidate_dirty=False
                    self.budget.check_time()
                    if deferred & {a.action_id for a in candidate.actions}:
                        raise ValueError('Scheduler violated a recorded action deferral')
                    if not validation.valid:
                        reasons.append('Independent validation failed');break
                    if mode=='template' or not self.reviewer_enabled:break
                    review=invoke('plan_reviewer' if mode=='multi' else 'single_agent',
                        {'plan':plan_view(candidate),'validation':validation.model_dump(),'arithmetic_checks':arithmetic_checks(candidate,scenario),'service_forecast':service_forecast(state,candidate),'review_feedback':review_feedback},Review,'review')
                    requested={aid for request in review.requests for aid in request.action_ids}
                    if review.decision=='approve' and requested<=deferred:
                        if requested:message('coordinator','review_audit',{'acknowledged_existing_holds':sorted(requested)})
                        break
                    if review.decision=='escalate' or revision==3:
                        reasons.extend(review.findings or ['Review did not approve within revision budget']);break
                    if not self.feedback_enabled:
                        reasons.append('Review requested revision; feedback disabled for ablation');break
                    if review.requests and requested-deferred:
                        if review.decision=='approve':
                            message('coordinator','review_audit',{'new_holds_require_replanning':sorted(requested-deferred),'original_decision':'approve'})
                        apply_requests(review,'plan_reviewer' if mode=='multi' else 'single_agent')
                        if reasons:break
                        candidate_dirty=True;review_feedback=None
                        continue
                    if review.decision=='revise' and review.revision_kind=='schedule' and not review.requests and self.planner=='greedy' and review.revision_request.strip():
                        self.planner='cp_sat';candidate_dirty=True;review_feedback=None
                        message('coordinator','deterministic_scheduler',{'revision_request':review.revision_request,'planner':'cp_sat'})
                        continue
                    exact_source_recheck=(review.revision_kind=='evidence' and set(review.evidence_ids)<=recognized_ids|{scenario.policy.evidence_id})
                    needs_clarification=(review.decision=='approve' or bool(review.requests) or not review.revision_request.strip()
                                         or review.revision_kind=='schedule' or (exact_source_recheck and review_feedback is None))
                    if needs_clarification:
                        review_feedback={'issue':'Review cannot be applied as returned; candidate remains unapproved.',
                            'allowed_responses':'Approve only the unchanged valid candidate with existing holds; revise with a concrete evidence correction or NEW typed defer_action; otherwise escalate.',
                            'active_holds':sorted(deferred),'requested_holds':sorted(requested),
                            'arithmetic_checks':arithmetic_checks(candidate,scenario),
                            'exact_report_checks':[{'report_id':f.evidence_ids[0],'target':f.target_id,'attribute':f.attribute,'value':f.value,'status':f.status} for f in recognized],
                            'resolved_observations':observations_view(state.resolved_observations),
                            'note':'Repeating an existing hold changes no constraint. Work end is work start plus duration; travel precedes work start. Never require simulator results before human approval.'}
                        message('coordinator','plan_reviewer' if mode=='multi' else 'single_agent',review_feedback)
                        continue
                    revised=invoke('network_investigator' if mode=='multi' else 'single_agent',{'reports':reports,'revision_request':review.revision_request,
                       'previous_facts':[f.model_dump() for f in state.facts]},FactBatch,'investigate')
                    state_version+=1
                    candidate_dirty=True;review_feedback=None
                    state=build_verified_state(scenario,revised.facts,state_version=state_version)
                    if mode!='template' and not state.unresolved_facts:assess_specialists()
                    if reasons:break
                    if state.unresolved_facts:
                        reasons.extend(state.unresolved_facts);break
                self.budget.check_time()
        except Exception as error:
            reasons.append(f'{type(error).__name__}: workflow stopped; inspect structured usage and evidence')
            candidate=None;validation=None
        result=RunResult(run_id=str(uuid4()),mode=mode,status='escalated' if reasons else 'awaiting_approval',
                         state=state,plan=candidate,validation=validation,messages=messages,
                         model_usage=list(self.budget.records),reasons=reasons,
                         metadata={"started_at_utc":started_at,"duration_seconds":time.monotonic()-self.budget.started,
                           "auxiliary_requests":list(self.budget.auxiliary_records),"raw_extraction_metrics":raw_extraction,"protocol_version":PROTOCOL_VERSION,"context_sha256":digest(context),"decision_effects":effects,
                           "deferred_action_ids":sorted(deferred),"input_hash":digest(scenario),"planner":self.planner,"reviewer_enabled":self.reviewer_enabled,
                           "feedback_enabled":self.feedback_enabled,"simulation_status":"not_integrated",
                           "transport":"none" if self.adapter is None else ("injected_test_client" if self.adapter.injected_client else "hosted"),
                           "budget":{"max_calls":self.budget.max_calls,"max_input_tokens":self.budget.max_input_tokens,
                                     "max_output_tokens":self.budget.max_output_tokens,"max_seconds":self.budget.max_seconds}})
        if self.trace_dir is not None:
            from .tracing import save_run
            save_run(result,self.trace_dir)
        return result

def approve(plan_id:str,state_version:int,decision:str,*,plan:Plan,state:VerifiedState,operator_id:str) -> Approval:
    if (plan_id,state_version)!=(plan.plan_id,state.state_version):raise ValueError('Stale plan or state')
    if not validate(plan,state).valid:raise ValueError('Cannot approve an invalid plan')
    return Approval(plan_id=plan_id,plan_hash=digest(plan),state_version=state_version,state_hash=digest(state),
                    decision=decision,operator_id=operator_id)

def check_approval(approval:Approval,plan:Plan,state:VerifiedState):
    if approval.decision!='approve' or (approval.plan_id,approval.state_version,approval.plan_hash,approval.state_hash)!=(plan.plan_id,state.state_version,digest(plan),digest(state)):
        raise ValueError('Approval missing, rejected or invalidated by a material change')
    if not validate(plan,state).valid:raise ValueError('Approved plan is no longer valid')


def approve_run(result:RunResult,operator_id:str)->Approval:
    """UI entry point: agent escalation cannot be bypassed by approving a candidate."""
    if result.status!='awaiting_approval' or result.plan is None or result.validation is None or not result.validation.valid:
        raise ValueError('Only a successfully reviewed, validated run can be approved')
    return approve(result.plan.plan_id,result.state.state_version,'approve',plan=result.plan,state=result.state,operator_id=operator_id)
