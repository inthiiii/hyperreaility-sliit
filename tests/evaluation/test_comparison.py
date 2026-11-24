import json
from pathlib import Path
import pytest
from project.evaluation import runner
from project.evaluation.comparison import paired_summary
from project.evaluation.hosted_check import main
from project.llm.client import HostedAdapter


def row(mode,score,repeat=0,**changes):
    return dict({'variant':mode,'scenario_id':'DEMO-005','repeat':repeat,'status':'completed',
                 'scoring_status':'scored','actual_weighted_downtime':score,'decision_effect_count':1,
                 'model_configuration':{'model':'selected'},'returned_models':['selected-snapshot']},**changes)


def test_paired_summary_reports_coverage_failures_effects_and_uncertainty():
    rows=[row('single',10),row('multi',8),row('single',12,1),row('multi',14,1),
          row('single',None,2,status='escalated',scoring_status='not_scored_escalated'),row('multi',5,2)]
    summary=paired_summary(rows)
    assert summary['eligible_pairs']==3 and summary['scored_comparable_pairs']==2
    assert summary['mean_single_minus_multi']==0 and summary['multi_wins']==summary['single_wins']==1
    assert len(summary['excluded_pairs'])==1 and summary['status_counts']['single']['escalated']==1
    assert summary['paired_bootstrap_95pct_interval'] is not None and not summary['claims_multi_agent_superiority']


@pytest.mark.parametrize('change',[{'model_configuration':{'model':'different'}},{'returned_models':['different']},{'returned_models':[]},{'returned_models':['snapshot-a','snapshot-b']}])
def test_model_mismatches_or_missing_usage_prevent_pooling(change):
    summary=paired_summary([row('single',20),row('multi',5,**change)])
    assert summary['scored_comparable_pairs']==0 and summary['mean_single_minus_multi'] is None


def test_smoke_requires_explicit_live_flag_before_loading_or_requesting(monkeypatch):
    monkeypatch.setattr('sys.argv',['hosted_check','--model','selected','--output','unused'])
    monkeypatch.setattr(HostedAdapter,'from_env',lambda **kwargs:pytest.fail('Unexpected API construction'))
    with pytest.raises(SystemExit) as error:main()
    assert error.value.code==2


def test_offline_manifest_freezes_protocol_runtime_and_comparison(tmp_path):
    path=Path(__file__).resolve().parents[2]/'data/processed/agent_inputs/demo/DEMO-005.json'
    runner.run_benchmark([path],tmp_path/'out',variants=['optimizer'],repeats=1)
    manifest=json.loads((tmp_path/'out/manifest.json').read_text())
    assert manifest['comparison_protocol']['stages']==['investigate','resources','priorities','review']
    assert manifest['runtime']['python'] and manifest['comparison_protocol']['max_revision_rounds']==3
    assert json.loads((tmp_path/'out/comparison.json').read_text())['scored_comparable_pairs']==0


def test_config_changes_between_jobs_fail_closed_without_switching_models(tmp_path,monkeypatch):
    import os
    from types import SimpleNamespace as NS
    from project.agents.extraction import template_facts
    from project.core.schemas import ScenarioInput
    monkeypatch.setenv('LLM_PROVIDER','openai');monkeypatch.setenv('LLM_MODEL','fake-model')
    monkeypatch.setenv('OPENAI_API_KEY','not-a-real-key')
    monkeypatch.delenv('LLM_BASE_URL',raising=False)
    path=Path(__file__).resolve().parents[2]/'data/processed/agent_inputs/demo/DEMO-005.json'
    case=ScenarioInput.model_validate_json(path.read_text());clients=[]
    def factory(budget):
        replies=iter([{'facts':[f.model_dump() for f in template_facts(case)]},
                      {'finding':'Resources checked','evidence_ids':['REP-001']},
                      {'finding':'Policy checked','evidence_ids':['REP-001']},
                      {'decision':'approve','findings':[],'evidence_ids':[]}])
        def create(**kwargs):
            return NS(id='injected',model='fake-model',usage=NS(prompt_tokens=100,completion_tokens=50),
                      choices=[NS(finish_reason='stop',message=NS(content=json.dumps(next(replies))))])
        client=NS(chat=NS(completions=NS(create=create)))
        a=HostedAdapter('openai','fake-model','not-a-real-key',budget=budget,client=client)
        clients.append(a)
        a.close=lambda:os.environ.__setitem__('LLM_MODEL','changed-model')
        return a
    monkeypatch.setattr(HostedAdapter,'from_env',factory)
    rows=runner.run_benchmark([path],tmp_path/'out',variants=['single','multi'],repeats=1,allow_live=True)
    assert len(clients)==1 and sorted(r['status'] for r in rows)==['completed','failed']
    assert all(r['model_configuration']['model']=='fake-model' for r in rows)
    failed=next(r for r in rows if r['status']=='failed')
    assert failed['model_calls']==0 and failed['actual_weighted_downtime'] is None
    assert (tmp_path/'out/attempts.jsonl').stat().st_mode & 0o777==0o600
    assert 'not-a-real-key' not in (tmp_path/'out/manifest.json').read_text()
