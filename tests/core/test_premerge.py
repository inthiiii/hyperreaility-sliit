import json
from pathlib import Path
import pytest
from project.core.coordinator import Coordinator,approve_run
from project.core.integration import CoreSession,IntegrationNotReady
from project.core.tracing import save_run,read_run,redact
from project.core.state import build_verified_state
from project.agents.extraction import template_facts
from project.llm.health import preflight
from project.llm.client import RunBudget
from project.evaluation.runner import run_benchmark
from test_models import adapter,batch,finding,review


def test_trace_roundtrip_private_and_tamper(load_case,tmp_path):
    result=Coordinator(trace_dir=tmp_path).run(load_case())
    path=tmp_path/(result.run_id+'.json')
    assert read_run(path)['run_id']==result.run_id
    assert path.stat().st_mode & 0o777==0o600
    value=json.loads(path.read_text());value['payload']['status']='corrupted';path.write_text(json.dumps(value))
    with pytest.raises(ValueError):read_run(path)


def test_trace_redaction():
    value=redact({'OPENAI_API_KEY':'private','nested':['Bearer private-secret','sk-example123'], 'normal':'visible'})
    assert 'private' not in json.dumps(value) and 'sk-example' not in json.dumps(value)
    assert value['normal']=='visible'


def test_failed_workflow_still_traced(load_case,tmp_path):
    result=Coordinator(adapter([RuntimeError('sk-secretDoNotLog')]),trace_dir=tmp_path).run(load_case(),'single')
    assert result.status=='escalated'
    text=(tmp_path/(result.run_id+'.json')).read_text()
    assert 'sk-secretDoNotLog' not in text
    assert read_run(tmp_path/(result.run_id+'.json'))['model_usage'][0]['error_type']=='RuntimeError'


def test_zero_call_coordinator_cannot_be_reused(load_case):
    c=Coordinator();c.run(load_case())
    with pytest.raises(ValueError):c.run(load_case())


def test_review_escalation_cannot_be_operator_approved(load_case):
    s=load_case();result=Coordinator(adapter([batch(s),finding(),finding(),review('escalate')])).run(s,'single')
    assert result.plan is not None and result.validation.valid
    with pytest.raises(ValueError):approve_run(result,'operator')


def test_simulator_waiting_boundary(load_case):
    session=CoreSession();session.prepare(Coordinator(),load_case());session.approve('operator')
    with pytest.raises(IntegrationNotReady):session.simulate()


def test_simulation_approval_mutation_and_replay(load_case):
    calls=[]
    def simulator(state,plan):
        calls.append(plan.plan_id);return {'fake_simulation':True}
    session=CoreSession(simulator);session.prepare(Coordinator(),load_case())
    with pytest.raises(ValueError):session.simulate()
    session.approve('operator');assert session.simulate()['fake_simulation']
    with pytest.raises(ValueError):session.simulate()
    assert len(calls)==1
    session.prepare(Coordinator(),load_case());assert session.approval is None
    assert session.current.state.state_version==2
    session.approve('operator');session.current.plan.explanation+=' changed'
    with pytest.raises(ValueError):session.simulate()


def test_failed_prepare_revokes_old_plan(load_case):
    session=CoreSession();session.prepare(Coordinator(),load_case());session.approve('operator')
    with pytest.raises(ValueError):session.prepare(Coordinator(),load_case(),'single')
    assert session.current is None and session.approval is None


def test_preflight_no_secret_or_model_guess():
    result=preflight({'OPENAI_API_KEY':'sk-do-not-output'})
    assert result['status']=='blocked' and result['model'] is None
    assert 'sk-' not in json.dumps(result) and not result['inference_performed']
    assert preflight({'LLM_MODEL':'chosen-model','OPENAI_API_KEY':'private'})['status']=='configured_unverified'
    assert preflight({'LLM_PROVIDER':'invalid'})['status']=='blocked'


def test_output_reservation_positive():
    for value in (0,-1,True,1.5):
        with pytest.raises(ValueError):RunBudget().reserve([],value)


def test_prompt_and_schema_fingerprints(load_case):
    s=load_case();result=Coordinator(adapter([batch(s),finding(),finding(),review()])).run(s,'single')
    assert result.metadata['transport']=='injected_test_client'
    assert all(len(r['prompt_sha256'])==64 and len(r['schema_sha256'])==64 for r in result.model_usage)


def test_scheduling_feedback_changes_action_plan(load_case):
    s=load_case()
    revision=json.dumps({'decision':'revise','findings':[], 'evidence_ids':['REP-001'],
        'revision_kind':'schedule','revision_request':'Optimize weighted service availability rather than earliest completion'})
    result=Coordinator(adapter([batch(s),finding(),finding(),revision,review()]),planner='greedy').run(s,'single')
    schedules=[m['finding'] for m in result.messages if m['sender']=='deterministic_scheduler']
    assert result.status=='awaiting_approval' and len(schedules)==2
    assert len(schedules[0]['actions'])>len(schedules[1]['actions'])


def test_no_reviewer_ablation(load_case):
    s=load_case();a=adapter([batch(s),finding(),finding()])
    result=Coordinator(a,reviewer_enabled=False).run(s,'multi')
    assert result.status=='awaiting_approval' and len(a.client.requests)==3
    assert not result.metadata['reviewer_enabled']


def test_no_feedback_ablation(load_case):
    s=load_case();a=adapter([batch(s),finding(),finding(),review('revise')])
    result=Coordinator(a,feedback_enabled=False).run(s,'multi')
    assert result.status=='escalated' and len(a.client.requests)==4


def test_evidence_revision_reassesses_specialists(load_case):
    s=load_case();a=adapter([batch(s),finding(),finding(),review('revise'),batch(s),finding(),finding(),review()])
    result=Coordinator(a,budget=a.budget).run(s,'multi')
    # Known usage replaces each completed reservation; both specialist rounds
    # and the final review must still occur under the unchanged whole-run caps.
    assert result.status=='awaiting_approval' and len(a.client.requests)==8
    assert sum(m['sender']=='field_resource_planner' for m in result.messages)==2


def test_known_fixture_wrong_value_cannot_be_verified(load_case):
    s=load_case();facts=template_facts(s);facts[0].value=not facts[0].value
    with pytest.raises(ValueError):build_verified_state(s,facts)


def test_missing_known_fixture_facts_are_retained(load_case):
    s=load_case();state=build_verified_state(s,[])
    assert len(state.facts)==len(template_facts(s))
    assert not state.unresolved_facts


def test_benchmark_manifest_and_independent_scores(tmp_path):
    source=Path(__file__).parent/'fixtures'/'DEMO-005.json'
    rows=run_benchmark([source],tmp_path/'experiment',repeats=1)
    assert len(rows)==2 and all(x['scoring_status']=='scored' for x in rows)
    assert all(x['actual_weighted_downtime']==5760 for x in rows)
    manifest=json.loads((tmp_path/'experiment'/'manifest.json').read_text())
    assert manifest['scoring_status']=='independent_incident_evaluator_connected'
    assert len(list((tmp_path/'experiment'/'runs').glob('*.json')))==2
    with pytest.raises(FileExistsError):run_benchmark([source],tmp_path/'experiment',repeats=1)


def test_benchmark_failure_retained(tmp_path,monkeypatch):
    source=Path(__file__).parent/'fixtures'/'DEMO-005.json'
    def fail(*args,**kwargs):raise RuntimeError('private exception')
    monkeypatch.setattr(Coordinator,'run',fail)
    rows=run_benchmark([source],tmp_path/'failed',repeats=1)
    assert len(rows)==2 and all(x['status']=='failed' for x in rows)
    assert 'private exception' not in (tmp_path/'failed'/'attempts.jsonl').read_text()


def test_benchmark_rejects_duplicate_and_unapproved_live(tmp_path):
    source=Path(__file__).parent/'fixtures'/'DEMO-005.json'
    with pytest.raises(ValueError):run_benchmark([source,source],tmp_path/'dup')
    with pytest.raises(ValueError):run_benchmark([source],tmp_path/'live',variants=['multi'])
    assert not (tmp_path/'live').exists()
