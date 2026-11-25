"""Benchmark plumbing for the v14 agent workflow on evidence v3 (scripted model, no API)."""
from pathlib import Path

import pytest

from project.agents import registry as R
from project.data.evaluator import EvaluatorLoader
from project.evaluation import runner
from project.llm.client import HostedAdapter

ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / 'releases' / 'evidence-v3-20261126' / 'data'


class LabelAdapter:
    """Answers with the case's hidden labels: tests plumbing and scoring, not model skill."""
    injected_client = True
    provider = 'openai'
    model = 'injected-test'

    def __init__(self, budget, labels):
        self.budget, self.labels = budget, labels

    def complete(self, role, payload, response_model, max_output=700, *, evidence_ids=None, history=None):
        self.budget.reserve([{'content': 'scripted'}], max_output)
        self.budget.records.append({'input_tokens': 7, 'output_tokens': 4, 'model': 'injected-test', 'role': role,
                                    'status': 'ok'})
        facts = [{'target_type': l['target_type'], 'target_id': l['target_id'], 'attribute': l['attribute'],
                  'value': l['reported_value'], 'evidence_ids': [l['report_id']]} for l in self.labels]
        if response_model is R.Extraction:
            return R.Extraction(facts=facts, ignored_reports=[], finding='scripted')
        if response_model is R.SingleAnalysis:
            return R.SingleAnalysis(facts=facts, ignored_reports=[], requests=[], questions=[],
                                    priority_proposals=[], finding='scripted')
        if response_model is R.SpecialistFinding:
            return R.SpecialistFinding(finding='ok', evidence_ids=[], requests=[], questions=[], priority_proposals=[])
        return R.PlanReview(decision='approve', fact_challenges=[], requests=[], findings=[], evidence_ids=[])

    def close(self):
        pass


@pytest.mark.parametrize('variant,calls', [('multi', 4), ('single', 2), ('no_reviewer', 3)])
def test_v14_variants_score_on_v3_with_truth_side_extraction_metrics(tmp_path, monkeypatch, variant, calls):
    sid = 'DEV-003'
    labels = EvaluatorLoader(V3 / 'evaluation/ground_truth').load(sid).expected_report_facts
    monkeypatch.setattr(runner, 'preflight', lambda: {'status': 'configured_unverified', 'provider': 'openai',
                                                      'model': 'injected-test'})
    monkeypatch.setattr(HostedAdapter, 'from_env', lambda budget=None: LabelAdapter(budget, labels))
    path = V3 / 'processed/agent_inputs/development' / f'{sid}.json'
    row = runner.run_benchmark([path], tmp_path, variants=[variant], repeats=1, allow_live=True, data_root=V3)[0]
    assert row['status'] == 'completed' and row['scoring_status'] == 'scored'
    assert row['model_calls'] == calls
    assert row['extraction']['initial']['f1'] == 1.0 and row['extraction']['labels'] == 3
    assert row['extraction']['injection_followed'] is False
    assert isinstance(row['actual_weighted_downtime'], (int, float))
