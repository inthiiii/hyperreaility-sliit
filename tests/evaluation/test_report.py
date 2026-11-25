"""Benchmark report: paired medians, bootstrap interval and no dropped attempts."""
import json

from project.evaluation import report as R


def row(case, variant, status, downtime, repeat=0):
    return {'scenario_id': case, 'variant': variant, 'repeat': repeat, 'status': status,
            'actual_weighted_downtime': downtime if status == 'completed' else None, 'model_calls': 4,
            'input_tokens': 1000, 'output_tokens': 100, 'duration_seconds': 1.0,
            'extraction': {'initial': {'f1': 1.0, 'distractor_claims': 0}, 'final': {'f1': 1.0},
                           'injection_followed': False, 'injection_flagged': True} if variant != 'optimizer' else None}


def test_report_pairs_on_shared_cases_and_keeps_failures(tmp_path):
    rows = [row('A', 'multi', 'completed', 100), row('A', 'single', 'completed', 200),
            row('B', 'multi', 'completed', 50), row('B', 'single', 'escalated', None),
            row('A', 'optimizer', 'completed', 300), row('B', 'optimizer', 'completed', 300),
            row('A', 'multi', 'completed', 120, 1)]
    (tmp_path / 'attempts.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
    (tmp_path / 'manifest.json').write_text(json.dumps({'model_configuration': {'model': 'm'}}))
    summary = R.write(tmp_path, {'in': 1.0, 'out': 2.0, 'date': '2026-11-25'})
    pair = next(p for p in summary['paired'] if (p['a'], p['b']) == ('multi', 'single'))
    assert pair['cases'] == 1 and pair['mean_diff'] == -90  # median of 100,120 is 110
    assert summary['variants']['single']['escalated'] == 1 and summary['variants']['single']['attempts'] == 2
    assert summary['variants']['multi']['mean_cost_usd'] == (1000 * 1.0 + 100 * 2.0) / 1e6
    text = (tmp_path / 'REPORT.md').read_text()
    assert 'multi vs single' in text and 'not independently human-reviewed' in text
    assert summary['claims_multi_agent_superiority'] is False
