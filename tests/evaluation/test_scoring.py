"""Simulator scoring is isolated, full-horizon, and never fabricated on failure."""
import csv
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from project.agents.extraction import template_facts
from project.core.schemas import Report
from project.evaluation import runner
from project.llm.client import HostedAdapter
from project.simulation.episode import IncidentEpisode

ROOT=Path(__file__).resolve().parents[2]


def input_path(sid):
    split='demo' if sid=='DEMO-005' else 'development'
    return ROOT/'data/processed/agent_inputs'/split/(sid+'.json')


def run(tmp_path, sid='DEMO-005', **kwargs):
    return runner.run_benchmark([input_path(sid)],tmp_path,variants=['optimizer'],repeats=1,**kwargs)[0]


def test_static_score_is_measured_and_audited(tmp_path,monkeypatch):
    def no_api(*args,**kwargs):raise AssertionError('Offline run constructed an API adapter')
    monkeypatch.setattr(HostedAdapter,'from_env',no_api)
    row=run(tmp_path)
    assert row['status']=='completed' and row['scoring_status']=='scored'
    assert row['actual_weighted_downtime']==5760 and row['actual_weighted_available_minutes']==720
    assert row['actual_unweighted_available_minutes']==240 and row['actual_unweighted_downtime_minutes']==3360
    assert row['actual_first_restoration_min']==30 and row['actual_services_available_at_horizon_end']==0
    assert row['model_calls']==row['input_tokens']==row['output_tokens']==0
    assert row['api_cost'] is None and row['approval_mode']=='automated_benchmark_operator'
    record=json.loads((tmp_path/row['episode_artifacts'][0]).read_text())
    assert record['approval']['plan_id']==record['result']['plan_id']
    assert record['result']['run_metadata']['planner_prediction_used'] is False
    assert json.loads((tmp_path/'summary.json').read_text())['scored']==1
    saved=list(csv.DictReader((tmp_path/'attempts.csv').open()))
    assert float(saved[0]['actual_weighted_downtime'])==5760


def test_dynamic_score_covers_two_approvals_without_resetting_horizon(tmp_path):
    row=run(tmp_path,'DEV-010')
    assert row['status']=='completed' and row['approved_episodes']==2
    assert row['actual_weighted_downtime']==9250 and row['actual_weighted_available_minutes']==7310
    records=[json.loads((tmp_path/path).read_text()) for path in row['episode_artifacts']]
    assert records[0]['result']['metrics']['weighted_downtime_min'] is None
    assert records[0]['result']['run_metadata']['observed_until_min']==60
    assert records[1]['approval']['state_version']>records[0]['approval']['state_version']
    assert records[1]['result']['metrics']['measured_duration_min']==720


@pytest.mark.parametrize('sid',['DEV-006','DEV-008'])
def test_unresolved_evidence_is_planned_around_and_scored(tmp_path,sid):
    # v14 policy: unknown or conflicting facts block only the affected work; the
    # baseline still produces a validated plan and an independent score.
    row=run(tmp_path,sid)
    assert row['status']=='completed' and row['scoring_status']=='scored'
    assert row['actual_weighted_downtime'] is not None and row['episode_artifacts']


def test_escalated_runs_never_get_a_downtime_score(tmp_path,monkeypatch):
    from project.core.orchestrator import AgentOrchestrator
    original=AgentOrchestrator._no_ai_baseline
    def failing(self,scenario,version):
        result=original(self,scenario,version)
        return result.model_copy(update={'status':'escalated','reasons':['forced for test']})
    monkeypatch.setattr(AgentOrchestrator,'_no_ai_baseline',failing)
    row=run(tmp_path,'DEV-006')
    assert row['status']=='escalated' and row['scoring_status']=='not_scored_escalated'
    assert row['actual_weighted_downtime'] is None and not row['episode_artifacts']


def test_episode_limit_keeps_prefix_but_not_a_final_score(tmp_path):
    row=run(tmp_path,'DEV-010',max_episodes=1)
    assert row['status']=='incomplete' and row['scoring_status']=='not_scored_episode_limit'
    assert row['actual_weighted_downtime'] is None and len(row['episode_artifacts'])==1


def test_missing_truth_is_a_retained_failed_attempt(tmp_path):
    data=tmp_path/'data';shutil.copytree(ROOT/'data/processed',data/'processed')
    output=tmp_path/'experiment'
    row=run(output,data_root=data)
    assert row['status']=='failed' and row['actual_weighted_downtime'] is None
    assert row['failure_phase']=='evaluator_input_binding'
    assert len((output/'attempts.jsonl').read_text().splitlines())==1


def test_same_id_with_changed_input_cannot_use_registered_truth(tmp_path):
    payload=json.loads(input_path('DEMO-005').read_text())
    payload['region_label']='Modified input with same ID'
    path=tmp_path/'case.json';path.write_text(json.dumps(payload))
    row=runner.run_benchmark([path],tmp_path/'out',variants=['optimizer'],repeats=1)[0]
    assert row['status']=='failed' and row['failure_phase']=='evaluator_input_binding'
    assert not row['episode_artifacts'] and row['actual_weighted_downtime'] is None


@pytest.mark.parametrize('damage',['prefix','nan','wrong_id','unbalanced'])
def test_unusable_evaluator_output_is_not_scored(tmp_path,monkeypatch,damage):
    advance=IncidentEpisode.advance
    def broken(self,*args,**kwargs):
        result=advance(self,*args,**kwargs)
        if damage=='prefix':result.run_metadata['measurement_scope']='elapsed_prefix'
        elif damage=='nan':result.metrics['weighted_downtime_min']=float('nan')
        elif damage=='wrong_id':result.plan_id='wrong-plan'
        else:result.metrics['weighted_downtime_min']+=1
        return result
    monkeypatch.setattr(IncidentEpisode,'advance',broken)
    row=run(tmp_path)
    assert row['status']=='failed' and row['actual_weighted_downtime'] is None


class FakeAdapter:
    """Injected transport-free single-agent replies, with real budget accounting."""
    injected_client=True
    provider='openai'
    model='injected-test'
    def __init__(self,budget,closed):self.budget=budget;self.closed=closed
    def complete(self,role,payload,response_model,max_output=700,*,evidence_ids=None):
        self.budget.reserve([{'content':'injected response test'}],max_output)
        self.budget.records.append({'input_tokens':5,'output_tokens':3,'model':'injected-test','role':role,'status':'ok'})
        if response_model.__name__=='FactBatch':
            reports=[Report.model_validate(r) for r in payload['reports']]
            return response_model(facts=template_facts(SimpleNamespace(reports=reports)))
        if response_model.__name__=='Finding':return response_model(finding='Inspected resources and policy',evidence_ids=['REP-001'])
        return response_model.model_validate({'decision':'approve','findings':[],'evidence_ids':[],'revision_request':''})
    def close(self):
        self.closed.append(True)
        raise RuntimeError('private cleanup detail')


def fake_hosted(monkeypatch):
    closed=[]
    monkeypatch.setattr(runner,'preflight',lambda:{'status':'configured_unverified','provider':'openai','model':'injected-test'})
    monkeypatch.setattr(HostedAdapter,'from_env',lambda budget=None:FakeAdapter(budget,closed))
    return closed


def test_calls_are_aggregated_across_replans_and_cleanup_failure_does_not_lose_rows(tmp_path,monkeypatch):
    closed=fake_hosted(monkeypatch)
    row=runner.run_benchmark([input_path('DEV-010')],tmp_path,variants=['matched_single'],repeats=1,allow_live=True)[0]
    assert row['status']=='completed' and row['model_calls']==8
    assert row['input_tokens']==40 and row['output_tokens']==24
    assert row['usage_complete'] and len(closed)==2 and len(row['cleanup_errors'])==2
    assert 'private cleanup detail' not in (tmp_path/'attempts.jsonl').read_text()


def test_whole_incident_budget_cannot_reset_at_replan(tmp_path,monkeypatch):
    fake_hosted(monkeypatch)
    monkeypatch.setattr(runner,'LIMITS',{**runner.LIMITS,'max_calls':4})
    row=runner.run_benchmark([input_path('DEV-010')],tmp_path,variants=['matched_single'],repeats=1,allow_live=True)[0]
    assert row['status']=='failed' and row['error_type']=='BudgetExceeded'
    assert row['failure_phase']=='budget' and row['model_calls']==4
    assert row['actual_weighted_downtime'] is None and len(row['episode_artifacts'])==1
