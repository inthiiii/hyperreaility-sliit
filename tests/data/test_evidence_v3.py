import json
import subprocess
import sys
from pathlib import Path

import pytest

from project.data.evaluator import EvaluatorLoader
from project.data.loader import CaseLoader
from project.simulation.engine import _check_truth

ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / 'releases' / 'evidence-v3-20261126' / 'data'
V2 = ROOT / 'releases' / 'evaluation-v2-20261125' / 'data'
loader = CaseLoader(V3 / 'processed' / 'agent_inputs')
truths = EvaluatorLoader(V3 / 'evaluation' / 'ground_truth')
IDS = loader.case_ids()


def test_release_matches_rebuild():
    result = subprocess.run([sys.executable, 'scripts/build_evidence_v3.py', '--check'], cwd=ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_all_v2_cases_present():
    v2 = CaseLoader(V2 / 'processed' / 'agent_inputs').case_ids()
    assert IDS == v2 and len(IDS) == 31


@pytest.mark.parametrize('case_id', IDS)
def test_case_valid_and_labels_bound(case_id):
    case = loader.load_case(loader.find(case_id))
    truth = truths.load(case_id)
    _check_truth(case, truth)
    reports = {r.report_id: r for r in case.reports}
    labelled = {l['report_id'] for l in truth.expected_report_facts}
    noise = {d['report_id'] for d in truth.distractor_reports}
    assert labelled | noise == set(reports) and not labelled & noise
    assert all(reports[r].source_type not in {'authoritative_snapshot', 'operator_confirmation',
                                              'confirmed_field_update'} for r in noise)
    for site in case.sites:
        assert site.code and site.district and site.lat and site.lon
        assert site.site_id not in ' '.join(r.text for r in case.reports)
    # Template sentences from v1/v2 must be gone so a regex cannot do the extraction.
    assert not any(' records S' in r.text or r.text.startswith('S0') for r in case.reports)


def test_inputs_keep_truth_out():
    for path in (V3 / 'processed' / 'agent_inputs').rglob('*.json'):
        text = path.read_text()
        for key in ('expected_report_facts', 'distractor_reports', 'future_events', 'truth_patch'):
            assert key not in text


def test_old_fixture_dumps_unchanged_by_optional_fields():
    """v2 content hashes depend on dumps; optional v3 fields must not appear for v2 cases."""
    case = CaseLoader(V2 / 'processed' / 'agent_inputs').load_case('demo/DEMO-005.json')
    for site in case.model_dump(mode='json', by_alias=True)['sites']:
        assert set(site) == {'site_id', 'label', 'x', 'y', 'coordinate_system'}
    truth = EvaluatorLoader(V2 / 'evaluation' / 'ground_truth').load('DEMO-005')
    assert 'distractor_reports' not in truth.model_dump()
