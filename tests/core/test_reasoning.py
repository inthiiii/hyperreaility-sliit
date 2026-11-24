"""Selected Luna reasoning settings are explicit, audited and parity-bound."""
import json
import pytest
from project.llm.client import HostedAdapter
from project.llm.health import preflight
from project.core.coordinator import FactBatch
from project.evaluation.runner import model_configuration
from test_models import FakeClient


def test_explicit_none_reaches_request_and_usage_record():
    client=FakeClient(['{"facts":[]}'])
    adapter=HostedAdapter('openai','gpt-6-luna','not-a-key',client=client,reasoning_effort='none')
    assert adapter.complete('network_investigator',{},FactBatch).facts==[]
    assert client.requests[0]['reasoning_effort']=='none'
    assert adapter.budget.records[0]['reasoning_effort']=='none'


def test_provider_default_is_not_silently_replaced():
    client=FakeClient(['{"facts":[]}'])
    adapter=HostedAdapter('openai','other-model','not-a-key',client=client)
    adapter.complete('test',{},FactBatch)
    assert 'reasoning_effort' not in client.requests[0]
    assert adapter.budget.records[0]['reasoning_effort']=='provider_default'


def test_invalid_reasoning_configuration_blocks_before_client_setup():
    result=preflight({'OPENAI_API_KEY':'not-a-key','LLM_MODEL':'gpt-6-luna','LLM_REASONING_EFFORT':'invalid'})
    assert result['status']=='blocked' and 'Unsupported LLM_REASONING_EFFORT' in result['reasons']
    with pytest.raises(ValueError):HostedAdapter('openai','gpt-6-luna','not-a-key',reasoning_effort='invalid')


def test_reasoning_choice_is_frozen_in_benchmark_configuration(monkeypatch):
    monkeypatch.setenv('LLM_MODEL','gpt-6-luna');monkeypatch.setenv('LLM_REASONING_EFFORT','none')
    assert model_configuration()['reasoning_effort']=='none'
    monkeypatch.setenv('LLM_REASONING_EFFORT','low')
    assert model_configuration()['reasoning_effort']=='low'


def test_provider_diagnostics_are_actionable_without_recording_secrets():
    class ProviderError(RuntimeError):
        status_code=400
        body={'error':{'code':'invalid_request','param':'input','message':'Rejected sk-private-value Bearer secret-value'}}
    client=FakeClient([ProviderError('not exposed')])
    adapter=HostedAdapter('openai','fake-model','not-a-key',client=client)
    with pytest.raises(ProviderError):adapter.complete('test',{},FactBatch)
    record=adapter.budget.records[0]
    assert record['provider_code']=='invalid_request' and record['provider_param']=='input'
    assert 'private-value' not in json.dumps(record) and 'secret-value' not in json.dumps(record)
