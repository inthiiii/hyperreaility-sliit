"""Held-out configuration freeze: any drift in data, prompts, model or caps stops the run."""
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from project.agents import registry as R
from project.evaluation import freeze as F
from project.evaluation import runner

V3 = Path(__file__).resolve().parents[2] / 'releases' / 'evidence-v3-20261126' / 'data'


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    monkeypatch.setenv('LLM_MODEL', 'gpt-6-luna')
    monkeypatch.setenv('LLM_API', 'responses')
    monkeypatch.setenv('LLM_REASONING_EFFORT', 'none')
    data = tmp_path / 'data'
    shutil.copytree(V3, data)
    path = tmp_path / 'FREEZE.json'
    record = F.create(data, path, runner.LIMITS, allow_dirty=True)
    return data, path, record


def test_freeze_records_everything_and_verifies(frozen):
    data, path, record = frozen
    assert len(record['files']) == 40 and record['model']['model'] == 'gpt-6-luna'
    assert set(record['protocol']['agents']) == {'network_investigator', 'field_resource_planner',
                                                 'service_priority_assessor', 'plan_reviewer'}
    assert 'OPENAI_API_KEY' not in path.read_text()
    assert F.verify(path, data)['eval_files'] == 40
    with pytest.raises(F.FreezeError, match='create-only'):
        F.create(data, path, runner.LIMITS, allow_dirty=True)


def test_data_prompt_model_and_limit_drift_are_detected(frozen, monkeypatch):
    data, path, _ = frozen
    case = next((data / 'processed/agent_inputs/candidate_evaluation').glob('*.json'))
    original = case.read_text()
    case.write_text(original.replace('NMS', 'NMS ', 1))
    with pytest.raises(F.FreezeError, match='files'):
        F.verify(path, data)
    case.write_text(original)
    monkeypatch.setattr(R, 'REVIEWER', replace(R.REVIEWER, task=R.REVIEWER.task + ' tuned'))
    with pytest.raises(F.FreezeError, match='protocol'):
        F.verify(path, data)
    monkeypatch.undo()
    monkeypatch.setenv('LLM_MODEL', 'another-model')
    with pytest.raises(F.FreezeError, match='model'):
        F.verify(path, data)


def test_runner_requires_freeze_or_review_for_held_out_cases(frozen, monkeypatch, tmp_path):
    data, path, _ = frozen
    monkeypatch.setenv('LLM_MODEL', 'gpt-6-luna')
    monkeypatch.setenv('LLM_API', 'responses')
    monkeypatch.setenv('LLM_REASONING_EFFORT', 'none')
    case = data / 'processed/agent_inputs/candidate_evaluation/EVAL2-001.json'
    with pytest.raises(ValueError, match='blocked'):
        runner.run_benchmark([case], tmp_path / 'a', variants=['optimizer'], repeats=1, data_root=data)
    rows = runner.run_benchmark([case], tmp_path / 'b', variants=['optimizer'], repeats=1, data_root=data, freeze=path)
    assert rows[0]['status'] in ('completed', 'escalated')
    import json
    manifest = json.loads((tmp_path / 'b' / 'manifest.json').read_text())
    assert manifest['evaluation_review']['mode'] == 'configuration_freeze'
