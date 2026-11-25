import json
from pathlib import Path
import pytest
from scripts.report_development import summarize,markdown


def batch(path,sid='DEV-001',source='fingerprint'):
    path.mkdir()
    manifest={'source_sha256':source,'model_configuration':{'model':'gpt-6-luna','reasoning_effort':'none'},
              'comparison_protocol':{'version':'fixed'},'whole_incident_limits':{},'variants':['single','multi'],
              'repeats':1,'cases':{sid:'input-hash'}}
    (path/'manifest.json').write_text(json.dumps(manifest))
    rows=[{'scenario_id':sid,'variant':v,'repeat':0,'status':'completed','scoring_status':'scored',
           'actual_weighted_downtime':100,'model_calls':4,'input_tokens':100,'output_tokens':20,
           'duration_seconds':1,'run_ids':[],'model_configuration':manifest['model_configuration'],
           'returned_models':['gpt-6-luna']} for v in ('single','multi')]
    (path/'attempts.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    return path


def test_complete_disjoint_batches_can_be_summarized_without_raw_prompts(tmp_path):
    result=summarize([batch(tmp_path/'a'),batch(tmp_path/'b','DEV-002')],2)
    assert result['attempts']==4 and result['case_count']==2
    assert result['paired_comparison']['ties']==2 and result['api_cost'] is None
    assert 'Development observations only' in markdown(result)
    assert 'input-hash' in json.dumps(result) and 'reports' not in result['jobs'][0]


@pytest.mark.parametrize('damage',['duplicate_case','different_source','partial','held_out'])
def test_incomparable_or_incomplete_batches_are_rejected(tmp_path,damage):
    a=batch(tmp_path/'a');b=batch(tmp_path/'b','DEV-002')
    if damage=='duplicate_case':b=batch(tmp_path/'c')
    elif damage=='different_source':
        p=b/'manifest.json';m=json.loads(p.read_text());m['source_sha256']='other';p.write_text(json.dumps(m))
    elif damage=='partial':(b/'attempts.jsonl').write_text('')
    else:
        p=b/'manifest.json';m=json.loads(p.read_text());m['cases']={'EVAL-001':'hidden'};p.write_text(json.dumps(m))
    with pytest.raises(ValueError):summarize([a,b])
