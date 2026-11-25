"""Review workflow acceptance; injected attestations below are tests, never real reviews."""
import csv
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import shutil
import pytest
from project.core.schemas import ScenarioInput
from project.core.state import digest
from project.evaluation import case_review as review
from project.evaluation import runner

ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture
def pack(tmp_path):
    root=tmp_path/'repo';shutil.copytree(ROOT/'data',root/'data')
    directory=tmp_path/'review';packet=review.prepare(root,directory)
    return root,directory,packet


def write_rows(directory,rows):
    with (directory/'reviews.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=review.FIELDS,lineterminator='\n')
        writer.writeheader();writer.writerows(rows)


def injected_attestations(directory):
    rows=review.read_reviews(directory/'reviews.csv')
    for row in rows:
        row.update(reviewer='Injected test reviewer, not a real sign-off',reviewed_at_utc='2026-01-01T00:00:00Z',
            is_case_author='NO',was_prompt_tuner='NO',used_for_tuning='NO',
            topology_resources_review='PASS',report_semantics_review='PASS',labels_outcomes_review='PASS',
            diversity_action='ACCEPT_LIMITATION',decision='APPROVED',
            notes='Synthetic unit-test declaration only; no genuine human review is claimed.')
    write_rows(directory,rows);return rows


def test_prepare_exposes_actual_diversity_risk_and_leaves_all_humans_pending(pack):
    root,directory,packet=pack
    assert packet['human_review']=='PENDING' and packet['model_calls']==0
    assert not (directory/'cards.md').read_bytes().endswith(b'\n\n')
    assert packet['held_out_validity']=='NOT_ESTABLISHED'
    assert len(packet['cases'])==20 and set(packet['category_counts'].values())=={2}
    assert packet['diversity']['cases_matching_development_topology_descriptor']==20
    assert packet['diversity']['reports_matching_development_text']==packet['diversity']['total_reports']==34
    assert all(row['decision']=='PENDING' and not row['reviewer'] for row in review.read_reviews(directory/'reviews.csv'))
    assert all(row['future_events_for_evaluator_review'] is not None for row in packet['cases'])
    assert digest(packet)==digest(review.build_packet(root))
    with pytest.raises(FileExistsError):review.prepare(root,directory)


def test_pending_review_cannot_create_release(pack,tmp_path):
    root,directory,_=pack;result,_,_=review.inspect(root,directory)
    assert result['status']=='BLOCKED' and result['issues']
    out=tmp_path/'release.json'
    with pytest.raises(ValueError,match='blocked'):review.release(root,directory,out)
    assert not out.exists()


@pytest.mark.parametrize('field,value',[
    ('reviewer','Codex'),('reviewer',''),('reviewed_at_utc','not-a-date'),
    ('reviewed_at_utc','2026-01-01T00:00:00+05:30'),
    ('reviewed_at_utc',(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()),
    ('is_case_author','YES'),('was_prompt_tuner','YES'),('used_for_tuning','UNKNOWN'),
    ('topology_resources_review','PENDING'),('labels_outcomes_review','FAIL'),
    ('report_semantics_review',''),('diversity_action',''),('decision','CHANGES_REQUIRED'),('notes','OK')])
def test_each_human_attestation_condition_is_required(pack,field,value):
    root,directory,_=pack;rows=injected_attestations(directory);rows[0][field]=value;write_rows(directory,rows)
    result,_,_=review.inspect(root,directory)
    assert result['status']=='BLOCKED' and result['issues']


@pytest.mark.parametrize('damage',['missing','duplicate','extra','stale_input','stale_truth'])
def test_coverage_and_exact_hashes_cannot_be_skipped(pack,damage):
    root,directory,_=pack;rows=injected_attestations(directory)
    if damage=='missing':rows.pop()
    elif damage=='duplicate':rows[-1]=dict(rows[0])
    elif damage=='extra':rows.append({**rows[0],'scenario_id':'UNREGISTERED'})
    elif damage=='stale_input':rows[0]['input_sha256']='0'*64
    else:rows[0]['truth_sha256']='0'*64
    write_rows(directory,rows)
    assert review.inspect(root,directory)[0]['status']=='BLOCKED'


@pytest.mark.parametrize('kind',['input','truth','raw','packet'])
def test_data_or_packet_drift_invalidates_reviews(pack,kind):
    root,directory,packet=pack;injected_attestations(directory)
    path=directory/'packet.json' if kind=='packet' else root/packet['cases'][0]['files'][kind]['path']
    path.write_text(path.read_text()+'\n')
    if kind=='packet':
        p=json.loads(path.read_text());p['human_review']='APPROVED';path.write_text(json.dumps(p))
    with pytest.raises(ValueError,match='drift'):review.inspect(root,directory)


def test_release_is_hash_bound_immutable_and_does_not_certify_independence(pack,tmp_path):
    root,directory,packet=pack;injected_attestations(directory);out=tmp_path/'release.json'
    envelope=review.release(root,directory,out)
    case=ScenarioInput.model_validate_json((root/packet['cases'][0]['files']['input']['path']).read_text())
    verified=review.validate_release(root,out,[case])
    assert verified['status']=='HUMAN_ATTESTATIONS_COMPLETE'
    assert verified['held_out_validity']=='NOT_ESTABLISHED_BY_SOFTWARE'
    assert 'Self-reported' in verified['independence']
    with pytest.raises(FileExistsError):review.release(root,directory,out)
    case.region_label='Altered after review'
    with pytest.raises(ValueError,match='not bound'):review.validate_release(root,out,[case])
    envelope['payload']['reviews'][0]['used_for_tuning']='YES'
    envelope['payload']['reviews_sha256']=digest(envelope['payload']['reviews'])
    envelope['sha256']=digest(envelope['payload']);out.write_text(json.dumps(envelope))
    with pytest.raises(ValueError,match='attestations'):review.validate_release(root,out,[])


def test_invalid_csv_schema_and_ambiguous_rows_are_rejected(pack):
    _,directory,_=pack
    (directory/'reviews.csv').write_text('scenario_id,status\nEVAL-001,APPROVED\n')
    with pytest.raises(ValueError,match='columns'):review.read_reviews(directory/'reviews.csv')
    (directory/'reviews.csv').write_text(','.join(review.FIELDS)+'\nEVAL-001\n')
    with pytest.raises(ValueError,match='Malformed'):review.read_reviews(directory/'reviews.csv')


@pytest.mark.parametrize('variant',['optimizer','single'])
def test_runner_blocks_unreviewed_eval_before_provider_or_output_creation(pack,tmp_path,monkeypatch,variant):
    root,_,packet=pack
    path=root/packet['cases'][0]['files']['input']['path']
    renamed=tmp_path/'innocent-name.json';renamed.write_bytes(path.read_bytes())
    def forbidden(*a,**kw):raise AssertionError('Provider/attempt must not be reached')
    monkeypatch.setattr(runner,'preflight',forbidden);monkeypatch.setattr(runner,'_attempt',forbidden)
    out=tmp_path/'out'
    with pytest.raises(ValueError,match='review-release'):
        runner.run_benchmark([renamed],out,variants=[variant],repeats=1,allow_live=True,data_root=root/'data')
    assert not out.exists()


def test_runner_records_review_binding_without_exposing_truth_to_case(pack,tmp_path,monkeypatch):
    root,directory,packet=pack;injected_attestations(directory)
    release=tmp_path/'release.json';review.release(root,directory,release)
    path=root/packet['cases'][0]['files']['input']['path']
    def injected_attempt(case,variant,repeat,*args):
        assert not hasattr(case,'evaluation_truth') and not hasattr(case,'future_events')
        return {'scenario_id':case.scenario_id,'variant':variant,'repeat':repeat,'status':'escalated',
            'scoring_status':'not_scored_escalated','actual_weighted_downtime':None,'model_calls':0,'returned_models':[]}
    monkeypatch.setattr(runner,'_attempt',injected_attempt)
    runner.run_benchmark([path],tmp_path/'out',variants=['optimizer'],repeats=1,
                         data_root=root/'data',review_release=release)
    manifest=json.loads((tmp_path/'out/manifest.json').read_text())
    assert manifest['evaluation_review']['selected_case_ids']==[packet['cases'][0]['scenario_id']]
    assert 'truth_patch' not in json.dumps(manifest)
    assert manifest['evaluation_review']['held_out_validity']=='NOT_ESTABLISHED_BY_SOFTWARE'


def test_non_template_wording_can_be_reviewed_without_inventing_semantic_verification(pack):
    root,_,packet=pack;case=packet['cases'][0]
    input_path=root/case['files']['input']['path'];raw_path=root/case['files']['raw']['path']
    s=json.loads(input_path.read_text());raw=json.loads(raw_path.read_text())
    s['reports'][0]['text']='Field inspection found the first site equipment unusable; replacement is needed.'
    raw['agent_input']['reports'][0]['text']=s['reports'][0]['text']
    input_path.write_text(json.dumps(s));raw_path.write_text(json.dumps(raw))
    from project.data.audit import audit
    with pytest.raises(ValueError,match='literal report'):audit(root)
    revised=review.build_packet(root)
    label=revised['cases'][0]['report_labels_for_human_check'][0]
    assert label['mechanical_label_check']=='UNPARSED_HUMAN_REVIEW_REQUIRED'
    assert revised['human_review']=='PENDING' and revised['held_out_validity']=='NOT_ESTABLISHED'


def test_unparsed_wording_does_not_allow_invalid_gold_target(pack):
    root,_,packet=pack;case=packet['cases'][0]
    p=root/case['files']['truth']['path'];truth=json.loads(p.read_text())
    truth['expected_report_facts'][0]['target_id']='NONEXISTENT'
    p.write_text(json.dumps(truth))
    raw_path=root/case['files']['raw']['path'];raw=json.loads(raw_path.read_text())
    raw['evaluation_truth']=truth;raw_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError,match='reference/type'):review.build_packet(root)


@pytest.mark.parametrize('kind',['input','truth'])
def test_review_cannot_bind_inconsistent_raw_and_processed_versions(pack,kind):
    root,_,packet=pack;case=packet['cases'][0]
    path=root/case['files'][kind]['path'];value=json.loads(path.read_text())
    if kind=='input':value['region_label']='Inconsistent source version'
    else:value['evaluation_notes'].append('Inconsistent source version')
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='disagrees with.*source'):review.build_packet(root)
