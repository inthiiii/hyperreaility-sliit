"""Release validation must detect drift without inventing independent review."""
import importlib.util
import json
from pathlib import Path
import shutil
import pytest

from project.data.audit import audit,freeze
from project.data.loader import CaseLoader,LoaderError
from scripts.check_data import check_frozen

ROOT=Path(__file__).resolve().parents[2]


def test_all_inputs_and_literal_fact_labels_audit_cleanly():
    report=audit(ROOT)
    assert report['case_count']==31 and report['human_review']=='PENDING'
    assert report['held_out_validity']=='NOT_ESTABLISHED'
    assert sum(row['report_labels_checked'] for row in report['cases'])>31


def test_freeze_is_immutable_and_detects_modified_data(tmp_path):
    shutil.copytree(ROOT/'data',tmp_path/'data')
    target=tmp_path/'docs/evaluation/FROZEN_DATASET.json'
    snapshot=freeze(tmp_path,target)
    assert len(snapshot['files'])==201
    check_frozen(tmp_path)
    with pytest.raises(FileExistsError):freeze(tmp_path,target)
    p=tmp_path/'data/processed/agent_inputs/demo/DEMO-005.json'
    p.write_text(p.read_text().replace('Fictional site 01','Changed site 01'))
    with pytest.raises(ValueError,match='Frozen dataset changed'):check_frozen(tmp_path)


@pytest.mark.parametrize('filename,function',[('prepare_data.py','prepare'),('generate_scenarios.py','generate'),('download_context.py','download')])
def test_preparation_cannot_overwrite_frozen_release(tmp_path,filename,function):
    path=tmp_path/'docs/evaluation/FROZEN_DATASET.json';path.parent.mkdir(parents=True);path.write_text('{}')
    spec=importlib.util.spec_from_file_location('release_test_script',ROOT/'scripts'/filename)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.ROOT=tmp_path
    with pytest.raises(ValueError,match='frozen'):getattr(module,function)()
    assert not (tmp_path/'data').exists()  # stopped before download or any data mutation


def test_loader_checks_filename_identity_without_echoing_input(tmp_path):
    path=tmp_path/'demo/WRONG.json';path.parent.mkdir()
    path.write_bytes((ROOT/'data/processed/agent_inputs/demo/DEMO-005.json').read_bytes())
    with pytest.raises(LoaderError,match='scenario_id disagrees'):CaseLoader(tmp_path).load_case(path)
    payload=json.loads(path.read_text());payload['sites'][0]['x']='sensitive-invalid-value'
    path.write_text(json.dumps(payload))
    with pytest.raises(LoaderError) as error:CaseLoader(tmp_path).load_case(path)
    assert 'sites.0.x' in str(error.value) and 'sensitive-invalid-value' not in str(error.value)


def test_loader_rejects_symlink_escape(tmp_path):
    approved=tmp_path/'inputs';(approved/'demo').mkdir(parents=True)
    outside=tmp_path/'outside.json';outside.write_bytes((ROOT/'data/processed/agent_inputs/demo/DEMO-005.json').read_bytes())
    (approved/'demo/DEMO-005.json').symlink_to(outside)
    with pytest.raises(LoaderError):CaseLoader(approved).load_case('demo/DEMO-005.json')


def test_preprocessing_reproduces_the_published_manifest_without_mutation(tmp_path,monkeypatch):
    import hashlib
    import contextlib
    import io
    from scripts import prepare_data
    from scripts.check_data import check_manifest
    shutil.copytree(ROOT/'data',tmp_path/'data')
    before={p.relative_to(tmp_path).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (tmp_path/'data').rglob('*') if p.is_file()}
    monkeypatch.setattr(prepare_data,'ROOT',tmp_path)
    with contextlib.redirect_stdout(io.StringIO()):prepare_data.prepare()
    after={p.relative_to(tmp_path).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
           for p in (tmp_path/'data').rglob('*') if p.is_file()}
    assert before==after
    assert check_manifest(tmp_path)==201
