"""AI self-review is never silently upgraded into independent human validation."""
import csv
import importlib.util
import json
from pathlib import Path
import shutil
import pytest
from scripts.build_evaluation_v2 import build,revised_case
from project.core.schemas import ScenarioInput
from project.core.state import digest
from project.data.evaluator import EvaluatorTruth
from project.evaluation import ai_case_review as ai
from project.evaluation import case_review as human
from project.evaluation import runner

ROOT=Path(__file__).resolve().parents[2]
RELEASE=ROOT/'releases/evaluation-v2-20261125'


@pytest.fixture
def revision(tmp_path):
    target=tmp_path/'revision';shutil.copytree(RELEASE,target);return target


def test_all_twenty_cases_have_checked_arithmetic_and_explicit_non_independence():
    report=ai.audit_revision(RELEASE)
    assert len(report['cases'])==20 and all(c['status']=='PASS' for c in report['cases'])
    assert report['independent_review'] is False and report['human_review']=='PENDING' and report['model_calls']==0
    assert report['diversity']=={'unique_topology_descriptors':20,'cases_matching_development_topology_descriptor':0,
                                'reports_matching_development_text':0,'total_reports':35}
    categories={c['category'] for c in report['cases']};assert len(categories)==10
    for case in report['cases']:
        if case['category']=='resource_loss_replanning':
            assert case['mechanism_checks']['unfinished_work']=='PAUSED_WITHOUT_COMPLETION_CREDIT'
            assert case['mechanism_checks']['prefix_full_score'] is None
            assert case['mechanism_checks']['no_work_approved_episodes']==2
        assert case['mechanism_checks']['stale_approval_rejected']


def test_deeper_topology_packet_hash_survives_json_roundtrip():
    packet=human.build_packet(RELEASE)
    assert any(int(depth)>=10 for case in packet['cases'] for depth in case['topology']['depth_counts'])
    assert digest(packet)==digest(json.loads(json.dumps(packet)))
    assert ai.validate_release(RELEASE,RELEASE/'AI_RELEASE.json',[])['status']=='AI_REVIEWED_FROZEN'


def test_reviews_are_twenty_ai_rows_and_human_sheet_stays_blank():
    packet=human.build_packet(RELEASE);rows=ai.checked_rows(RELEASE,packet)
    assert len(rows)==20
    assert all(r['reviewer_kind']=='AI' and r['decision']=='AI_REVIEWED' and r['independent_review']=='NO' and r['is_case_author']=='YES' for r in rows)
    pending=human.read_reviews(RELEASE/'review/human/reviews.csv')
    assert len(pending)==20 and all(r['decision']=='PENDING' and not r['reviewer'] for r in pending)
    with pytest.raises(ValueError,match='Invalid review release'):
        human.validate_release(RELEASE,RELEASE/'AI_RELEASE.json',[])


def test_builder_reproduces_frozen_dataset_bytes_and_cannot_overwrite(tmp_path):
    target=tmp_path/'rebuilt';build(target)
    for source in (RELEASE/'data').rglob('*'):
        if source.is_file():assert source.read_bytes()==(target/source.relative_to(RELEASE)).read_bytes()
    assert (target/'BLUEPRINT.json').read_bytes()==(RELEASE/'BLUEPRINT.json').read_bytes()
    with pytest.raises(FileExistsError):build(target)


@pytest.mark.parametrize('damage',['data','extra','review','false_human','unsafe_path'])
def test_frozen_release_rejects_data_review_and_claim_tampering(revision,damage):
    release=revision/'AI_RELEASE.json'
    if damage=='data':
        p=next((revision/'data/processed/agent_inputs/candidate_evaluation').glob('*.json'));p.write_text(p.read_text()+'\n')
    elif damage=='extra':(revision/'data/unregistered.json').write_text('{}')
    elif damage=='review':
        p=revision/'review/reviews.csv';p.write_text(p.read_text().replace('AI_REVIEWED','APPROVED',1))
    else:
        envelope=json.loads(release.read_text())
        if damage=='false_human':envelope['payload']['independent_review']=True
        else:envelope['payload']['files'][0]['path']='../outside'
        envelope['sha256']=digest(envelope['payload']);release.write_text(json.dumps(envelope))
    with pytest.raises(ValueError):ai.validate_release(revision,release,[])


def test_gold_label_cannot_disagree_with_visible_report_meaning():
    raw,_=revised_case(0);s=ScenarioInput.model_validate(raw['agent_input']);t=EvaluatorTruth.model_validate(raw['evaluation_truth'])
    t.expected_report_facts[0]['reported_value']=True
    with pytest.raises(ValueError,match='contradicts'):ai.labelled_facts(s,t)


@pytest.mark.parametrize('filename,function',[('prepare_data.py','prepare'),('generate_scenarios.py','generate'),('download_context.py','download')])
def test_ai_freeze_prevents_regeneration_before_any_mutation(tmp_path,filename,function):
    (tmp_path/'AI_RELEASE.json').write_text('{}')
    spec=importlib.util.spec_from_file_location('ai_guard_test',ROOT/'scripts'/filename)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.ROOT=tmp_path
    with pytest.raises(ValueError,match='frozen'):getattr(module,function)()
    assert not (tmp_path/'data').exists()


def test_frozen_release_is_create_only_and_preserves_source_revision():
    original=(RELEASE/'AI_RELEASE.json').read_bytes()
    with pytest.raises(FileExistsError):ai.freeze(RELEASE,RELEASE/'AI_RELEASE.json')
    assert (RELEASE/'AI_RELEASE.json').read_bytes()==original


def test_runner_requires_explicit_ai_mode_and_records_truthful_scope(tmp_path,monkeypatch):
    path=RELEASE/'data/processed/agent_inputs/candidate_evaluation/EVAL2-001.json'
    release=RELEASE/'AI_RELEASE.json'
    with pytest.raises(ValueError,match='Invalid review release'):
        runner.run_benchmark([path],tmp_path/'blocked',variants=['optimizer'],repeats=1,
                             data_root=RELEASE/'data',review_release=release)
    assert not (tmp_path/'blocked').exists()
    def injected_attempt(case,variant,repeat,*args):
        assert not hasattr(case,'evaluation_truth')
        return {'scenario_id':case.scenario_id,'variant':variant,'repeat':repeat,'status':'escalated',
                'scoring_status':'not_scored_escalated','actual_weighted_downtime':None,'model_calls':0,'returned_models':[]}
    monkeypatch.setattr(runner,'_attempt',injected_attempt)
    runner.run_benchmark([path],tmp_path/'engineering',variants=['optimizer'],repeats=1,
                         data_root=RELEASE/'data',review_release=release,allow_ai_reviewed=True)
    manifest=json.loads((tmp_path/'engineering/manifest.json').read_text())
    assert manifest['evaluation_review']['independent_review'] is False
    assert manifest['evaluation_review']['human_review']=='PENDING'
    assert manifest['evaluation_review']['held_out_validity']=='NOT_ESTABLISHED'
    assert 'truth_patch' not in json.dumps(manifest)


def test_review_and_freeze_can_be_reproduced_without_a_human_signature(tmp_path):
    target=tmp_path/'fresh';build(target);ai.record_review(target)
    ai.freeze(target,target/'AI_RELEASE.json')
    result=ai.validate_release(target,target/'AI_RELEASE.json',[])
    assert result['status']=='AI_REVIEWED_FROZEN' and result['independent_review'] is False
