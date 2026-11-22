import json
from types import SimpleNamespace as NS
import pytest
from project.llm.client import HostedAdapter,RunBudget,BudgetExceeded
from project.core.coordinator import Coordinator,FactBatch
from project.agents.extraction import template_facts

class FakeClient:
    def __init__(self,replies):
        self.replies=iter(replies);self.requests=[]
        self.chat=NS(completions=NS(create=self.create))
    def create(self,**kwargs):
        self.requests.append(kwargs);value=next(self.replies)
        if isinstance(value,Exception):raise value
        return NS(id='fake-request',model='fake-model',usage=NS(prompt_tokens=100,completion_tokens=50),
            choices=[NS(finish_reason='stop',message=NS(content=value))])
    def close(self):pass

def adapter(replies,budget=None):
    return HostedAdapter('openai','fake-model','fake-key',client=FakeClient(replies),budget=budget)

def batch(s):return json.dumps({'facts':[f.model_dump() for f in template_facts(s)]})
def finding():return json.dumps({'finding':'Reviewed resource constraints','evidence_ids':['REP-001'],'clarification_required':False})
def review(decision='approve'):return json.dumps({'decision':decision,'findings':[],'evidence_ids':['REP-001'],'revision_request':'Recheck report facts' if decision=='revise' else ''})

def test_schema_repair_counts_both_attempts():
    a=adapter(['bad json','{"facts":[]}'])
    assert a.complete('test',{},FactBatch).facts==[]
    assert a.budget.calls==2 and len(a.budget.records)==2
    assert a.budget.records[0]['status']=='schema_error'

def test_transport_error_is_recorded():
    a=adapter([RuntimeError('offline')])
    with pytest.raises(RuntimeError):a.complete('test',{},FactBatch)
    assert a.budget.calls==1 and a.budget.records[0]['status']=='error'

def test_budget_prevents_second_call():
    a=adapter(['{"facts":[]}'],RunBudget(max_calls=1))
    a.complete('test',{},FactBatch)
    with pytest.raises(BudgetExceeded):a.complete('test',{},FactBatch)
    assert len(a.client.requests)==1

def test_input_cap_stops_before_transport():
    a=adapter([],RunBudget(max_input_tokens=10))
    with pytest.raises(BudgetExceeded):a.complete('test',{},FactBatch)
    assert not a.client.requests

def test_model_configuration_required():
    with pytest.raises(ValueError):HostedAdapter('openai','','')

def test_single_agent_can_review_and_revise(load_case):
    s=load_case();a=adapter([batch(s),review('revise'),batch(s),review()])
    r=Coordinator(a).run(s,'single')
    assert r.status=='awaiting_approval' and len(r.model_usage)==4
    roles={m['sender'] for m in r.messages}
    assert 'single_agent' in roles and 'plan_reviewer' not in roles

def test_multi_agent_messages_are_real_adapter_calls(load_case):
    s=load_case();a=adapter([batch(s),finding(),finding(),review()])
    r=Coordinator(a).run(s,'multi')
    assert r.status=='awaiting_approval' and len(a.client.requests)==4
    roles={m['sender'] for m in r.messages}
    assert {'network_investigator','field_resource_planner','service_priority_assessor','plan_reviewer'}<=roles

def test_hallucinated_evidence_escalates(load_case):
    s=load_case();facts=template_facts(s);facts[0].evidence_ids=['INVENTED']
    a=adapter([json.dumps({'facts':[f.model_dump() for f in facts]})])
    r=Coordinator(a).run(s,'single')
    assert r.status=='escalated' and r.plan is None

def test_no_silent_template_fallback(load_case):
    with pytest.raises(ValueError):Coordinator().run(load_case(),'single')

def test_exhausted_run_cannot_reach_approval(load_case):
    s=load_case();a=adapter([batch(s)],RunBudget(max_calls=1))
    r=Coordinator(a).run(s,'multi')
    assert r.status=='escalated' and r.plan is None

def test_revision_round_limit(load_case):
    s=load_case();a=adapter([batch(s),review('revise'),batch(s),review('revise'),batch(s),review('revise'),batch(s),review('revise')])
    r=Coordinator(a).run(s,'single')
    assert r.status=='escalated'
    assert len(a.client.requests)<=8

def test_reported_usage_limit_cannot_authorize(load_case):
    s=load_case();a=adapter([batch(s)])
    original=a.client.create
    def oversized(**kw):
        response=original(**kw);response.usage.completion_tokens=5000;return response
    a.client.chat.completions.create=oversized
    r=Coordinator(a).run(s,'single')
    assert r.status=='escalated' and r.plan is None
