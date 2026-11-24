import json
from types import SimpleNamespace as NS
import pytest
from project.core.coordinator import FactBatch
from project.llm.client import HostedAdapter,RunBudget,BudgetExceeded


class ResponsesClient:
    def __init__(self,replies=('{}',),count=100,status='completed'):
        self.replies=iter(replies);self.count_value=count;self.status=status
        self.counts=[];self.generations=[]
        self.responses=NS(input_tokens=NS(count=self.count),create=self.create)
    def count(self,**kwargs):
        self.counts.append(kwargs)
        if isinstance(self.count_value,Exception):raise self.count_value
        return NS(input_tokens=self.count_value)
    def create(self,**kwargs):
        self.generations.append(kwargs)
        return NS(id='injected-response',model='gpt-6-luna',status=self.status,output_text=next(self.replies),
                  usage=NS(input_tokens=self.count_value,output_tokens=50))
    def close(self):pass


def make(client,budget=None):
    return HostedAdapter('openai','gpt-6-luna','not-a-key',client=client,budget=budget,
                         reasoning_effort='none',api_mode='responses')


def test_responses_uses_counted_payload_and_records_real_usage_not_bytes():
    c=ResponsesClient(['{"facts":[]}']);a=make(c)
    a.complete('investigator',{'large':'x'*10000},FactBatch)
    assert c.counts[0]['input']==c.generations[0]['input']
    assert c.counts[0]['text']==c.generations[0]['text']=={'format':{'type':'json_object'}}
    assert c.generations[0]['reasoning']=={'effort':'none'} and c.generations[0]['store'] is False
    assert a.budget.input_reserved==100 and a.budget.calls==1
    assert a.budget.records[0]['input_count_method']=='server_exact'
    assert a.budget.auxiliary_records[0]['kind']=='input_token_count'


def test_oversized_exact_count_blocks_generation():
    c=ResponsesClient(['{"facts":[]}'],count=24001);a=make(c)
    with pytest.raises(BudgetExceeded):a.complete('test',{},FactBatch)
    assert not c.generations and a.budget.calls==0 and len(a.budget.auxiliary_records)==1


def test_call_cap_blocks_before_auxiliary_request():
    c=ResponsesClient(['{"facts":[]}']);a=make(c,RunBudget(max_calls=1))
    a.complete('test',{},FactBatch)
    with pytest.raises(BudgetExceeded):a.complete('test',{},FactBatch)
    assert len(c.counts)==len(c.generations)==1


def test_count_failure_is_recorded_without_fallback_or_secret_text():
    c=ResponsesClient(count=RuntimeError('sk-never-print'));a=make(c)
    with pytest.raises(RuntimeError):a.complete('test',{},FactBatch)
    assert not c.generations and a.budget.calls==0
    assert a.budget.auxiliary_records[0]['error_type']=='RuntimeError'
    assert 'never-print' not in json.dumps(a.budget.auxiliary_records)


def test_schema_repair_recounts_and_uses_same_generation_budget():
    c=ResponsesClient(['bad JSON','{"facts":[]}']);a=make(c)
    assert a.complete('test',{},FactBatch).facts==[]
    assert a.budget.calls==2 and len(c.counts)==2 and len(a.budget.records)==2
    assert a.budget.records[0]['status']=='schema_error'


def test_incomplete_response_retains_usage_and_cannot_reach_a_typed_result():
    c=ResponsesClient(['{"facts":[]}'],status='incomplete');a=make(c)
    with pytest.raises(ValueError):a.complete('test',{},FactBatch)
    assert a.budget.records[0]['output_tokens']==50 and a.budget.records[0]['status']=='error'


def test_openrouter_cannot_silently_take_openai_responses_path():
    with pytest.raises(ValueError):HostedAdapter('openrouter','gpt-6-luna','not-a-key',api_mode='responses')
