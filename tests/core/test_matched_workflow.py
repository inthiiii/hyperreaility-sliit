"""Fair tool access and causal, conservative specialist effects (no live API)."""
import json
from pathlib import Path
import pytest
from project.core.coordinator import Coordinator, approve_run
from project.core.state import digest
from project.core.schemas import ScenarioInput
from project.agents.extraction import template_facts
from project.evaluation.extraction import extraction_metrics
from project.llm.client import RunBudget, BudgetExceeded
from test_models import adapter, batch, finding, review


def hold(action='GEN-G1-S02', evidence='REP-001'):
    return {'kind':'defer_action','action_ids':[action],'evidence_ids':[evidence],
            'reason':'Synthetic influence test: retain this action for operator investigation.'}


def finding_with(request):
    return json.dumps({'finding':'Conservative hold requested','evidence_ids':['REP-001'],
                       'requests':[request]})


def test_single_and_multi_have_equal_stages_context_tools_and_output_caps(load_case):
    scenario=load_case();payloads=[]
    for mode in ('single','multi'):
        a=adapter([batch(scenario),finding(),finding(),review()])
        result=Coordinator(a).run(scenario,mode)
        assert result.status=='awaiting_approval' and result.validation.valid
        requests=a.client.requests
        payloads.append([json.loads(r['messages'][1]['content']) for r in requests])
        assert [r['max_completion_tokens'] for r in requests]==[700,400,400,400]
        assert all(r['response_format']=={'type':'json_object'} for r in requests)
        assert [p['stage'] for p in payloads[-1]]==['investigate','resources','priorities','review']
        assert len({p['context_sha256'] for p in payloads[-1]})==1
        assert len({m['sender'] for m in result.messages if 'agent' in m['sender'] or m['sender'] in ('network_investigator','field_resource_planner','service_priority_assessor','plan_reviewer')})==(1 if mode=='single' else 4)
    for left,right in zip(*payloads):
        assert left['shared_context']==right['shared_context']
        assert left['reports']==right['reports']
        assert left['task']==right['task'] and left['resolved_observations']==right['resolved_observations']
        assert 'future_events' not in json.dumps(left) and 'ground_truth' not in json.dumps(left)


@pytest.mark.parametrize('mode',['single','multi'])
@pytest.mark.parametrize('stage',['resources','priorities'])
def test_specialist_deferral_changes_validated_plan_and_versions_state(load_case,mode,stage):
    scenario=load_case();before=digest(scenario)
    plain=Coordinator(adapter([batch(scenario),finding(),finding(),review()])).run(scenario,mode)
    answers=[batch(scenario),finding(),finding(),review()]
    answers[1 if stage=='resources' else 2]=finding_with(hold())
    changed=Coordinator(adapter(answers)).run(scenario,mode)
    assert plain.plan.actions and plain.plan.actions[0].action_id=='GEN-G1-S02'
    assert changed.status=='awaiting_approval' and changed.validation.valid
    assert 'GEN-G1-S02' not in {a.action_id for a in changed.plan.actions}
    assert changed.state.state_version>plain.state.state_version
    assert changed.metadata['decision_effects'][0]['request']['evidence_ids']==['REP-001']
    assert changed.metadata['decision_effects'][0]['operational_fact_verified'] is False
    assert digest(scenario)==before and changed.state.scenario.policy==scenario.policy
    approval=approve_run(changed,'test operator')
    assert approval.state_version==changed.state.state_version
    assert any('GEN-G1-S02' in text for text in changed.plan.unmet_needs)


@pytest.mark.parametrize('directive',[hold('INVENTED'),hold(evidence='INVENTED')])
def test_hallucinated_action_or_evidence_cannot_influence_or_reach_approval(load_case,directive):
    scenario=load_case();result=Coordinator(adapter([batch(scenario),finding_with(directive)])).run(scenario,'multi')
    assert result.status=='escalated' and not result.metadata['decision_effects']
    with pytest.raises(ValueError):approve_run(result,'operator')


def test_reviewer_constraint_causes_cp_sat_revision_instead_of_message_only(load_case):
    scenario=load_case()
    revise=json.dumps({'decision':'revise','findings':['Investigate before allocation'],
        'evidence_ids':['REP-001'],'revision_kind':'schedule','revision_request':'Defer generator action',
        'requests':[hold()]})
    a=adapter([batch(scenario),finding(),finding(),revise,review()])
    result=Coordinator(a).run(scenario,'multi')
    schedules=[m['finding'] for m in result.messages if m['sender']=='deterministic_scheduler']
    assert result.status=='awaiting_approval' and len(schedules)==2
    assert any(a['action_id']=='GEN-G1-S02' for a in schedules[0]['actions'])
    assert all(a['action_id']!='GEN-G1-S02' for a in schedules[1]['actions'])
    assert schedules[0]['actions']!=schedules[1]['actions']
    assert schedules[1]['state_version']>schedules[0]['state_version']


def test_no_feedback_does_not_silently_ignore_a_specialist_request(load_case):
    scenario=load_case();a=adapter([batch(scenario),finding_with(hold()),finding()])
    result=Coordinator(a,feedback_enabled=False).run(scenario,'multi')
    assert result.status=='escalated' and result.plan is None
    assert not result.metadata['decision_effects']


def test_token_reservations_reconcile_but_unknown_requests_remain_reserved():
    b=RunBudget(max_input_tokens=1000,max_output_tokens=1000)
    n=b.reserve([{'content':'x'*300}],400)
    b.reconcile(n,400,50,20)
    assert b.input_reserved==50 and b.output_reserved==20
    b.reserve([{'content':'x'*500}],400) # unknown transport failure keeps reservation
    assert b.input_reserved==614 and b.output_reserved==420
    with pytest.raises(BudgetExceeded):b.reserve([{'content':'x'*400}],400)


@pytest.mark.parametrize('usage',[(True,2),(-1,2),(2,3.5)])
def test_bad_usage_is_rejected_and_not_treated_as_free(usage):
    b=RunBudget();n=b.reserve([{'content':'text'}],400)
    with pytest.raises(ValueError):b.reconcile(n,400,*usage)
    assert b.input_reserved==n and b.output_reserved==400


def test_raw_extraction_metric_does_not_credit_resolver_template_fill(load_case):
    scenario=load_case()
    result=Coordinator(adapter([json.dumps({'facts':[]}),finding(),finding(),review()])).run(scenario,'single')
    assert result.status=='awaiting_approval' and result.state.facts
    assert result.metadata['raw_extraction_metrics']['f1']==0
    correct=extraction_metrics(scenario,template_facts(scenario))
    assert correct['f1']==1 and correct['raw_model_output_only']


def test_twenty_site_development_case_completes_four_stages_with_known_usage():
    path=Path(__file__).resolve().parents[2]/'data/processed/agent_inputs/development/DEV-010.json'
    scenario=ScenarioInput.model_validate_json(path.read_text())
    a=adapter([batch(scenario),finding(),finding(),review()])
    result=Coordinator(a).run(scenario,'multi')
    assert result.status=='awaiting_approval' and len(a.client.requests)==4
    assert a.budget.input_reserved==400 and a.budget.output_reserved==200


def test_no_feedback_ablation_removes_cross_agent_findings(load_case):
    scenario=load_case();a=adapter([batch(scenario),finding(),finding(),review()])
    result=Coordinator(a,feedback_enabled=False).run(scenario,'multi')
    assert result.status=='awaiting_approval'
    assert all(json.loads(r['messages'][1]['content'])['agent_findings']==[] for r in a.client.requests)


def test_reported_overspend_stays_in_failure_usage_record(load_case):
    scenario=load_case();a=adapter([batch(scenario)])
    create=a.client.create
    def oversized(**kwargs):
        reply=create(**kwargs);reply.usage.completion_tokens=5000;return reply
    a.client.chat.completions.create=oversized
    result=Coordinator(a).run(scenario,'single')
    assert result.status=='escalated' and result.model_usage[0]['output_tokens']==5000
    assert result.model_usage[0]['error_type']=='BudgetExceeded'


def test_compact_schema_retains_fields_named_like_schema_metadata():
    from pydantic import BaseModel
    from project.llm.client import response_schema
    class NamedFields(BaseModel):
        title:str
        description:str
        default:str
    schema=response_schema(NamedFields)
    assert set(schema['properties'])=={'title','description','default'}
    assert set(schema['required'])=={'title','description','default'}
