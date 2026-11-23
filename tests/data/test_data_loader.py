"""Reference integrity, unknown preservation, provenance and answer isolation."""
import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from project.data.evaluator import EvaluatorLoader
from project.data.loader import REPO_ROOT, CaseLoader, LoaderError, load_case

DATA = REPO_ROOT / 'data'
HIDDEN_KEYS = {'evaluation_truth', 'expected_report_facts', 'future_events', 'truth_patch',
               'category', 'seed', 'missing_facts', 'evaluation_notes'}
loader = CaseLoader()
CASES = loader.case_ids()


def keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from keys(v)


def test_inventory_matches_starter_pack():
    assert len(CASES) == 31
    splits = {p.name: len(list(p.glob('*.json'))) for p in (DATA / 'processed/agent_inputs').iterdir()}
    assert splits == {'demo': 1, 'development': 10, 'candidate_evaluation': 20}


def test_starter_check_script_passes():
    out = subprocess.run([sys.executable, '-I', str(REPO_ROOT / 'scripts/check_data.py')],
                         capture_output=True, text=True, cwd=REPO_ROOT)
    assert out.returncode == 0, out.stderr
    assert out.stdout.startswith('PASS')


@pytest.mark.parametrize('case', CASES)
def test_case_loads_and_truth_references_match(case):
    scenario = load_case(loader.find(case))
    truth = EvaluatorLoader().load(case)
    assert scenario.scenario_id == truth.scenario_id == case
    assert set(truth.sites) == {s.site_id for s in scenario.sites}
    assert set(truth.links) == {l.link_id for l in scenario.links}
    assert set(truth.roads) == {r.road_id for r in scenario.roads}
    assert truth.crews == [] or {c.crew_id for c in truth.crews} == {c.crew_id for c in scenario.crews}
    assert len(scenario.crews) == 2 and len(scenario.generators) == 1
    assert scenario.horizon_min == 720
    site_ids = {s.site_id for s in scenario.sites}
    assert all(sv.site_id in site_ids for sv in scenario.services)
    for ev in truth.future_events:
        assert ev.truth_patch.crew_id in {c.crew_id for c in scenario.crews}


@pytest.mark.parametrize('case', CASES)
def test_unknowns_preserved_between_raw_and_processed(case):
    split = loader.find(case).parent.name
    raw = json.loads((DATA / 'raw/synthetic' / split / f'{case}.json').read_text(encoding='utf-8'))
    processed = json.loads(loader.find(case).read_text(encoding='utf-8'))
    assert processed['observed_state'] == raw['agent_input']['observed_state']
    assert processed['reports'] == raw['agent_input']['reports']      # stale/conflicting reports retained


def test_demo_unknowns_are_null_not_guessed():
    s = load_case('demo/DEMO-005.json')
    assert s.observed_state.sites['S01'].grid_power_ok is None
    assert s.observed_state.sites['S02'].grid_power_ok is None
    assert s.observed_state.links['L01'] is None
    assert sum(1 for c in CASES if _null_count(c)) > 0


def _null_count(case):
    s = load_case(loader.find(case))
    o = s.observed_state
    return sum(v is None for v in [*o.links.values(), *o.roads.values(),
                                   *[x for st in o.sites.values() for x in (st.equipment_ok, st.grid_power_ok)]])


@pytest.mark.parametrize('case', CASES)
def test_agent_inputs_contain_no_answers_or_real_coordinates(case):
    raw = json.loads(loader.find(case).read_text(encoding='utf-8'))
    assert not set(keys(raw)) & HIDDEN_KEYS
    assert not set(keys(raw)) & {'lon', 'lng', 'lat', 'longitude', 'latitude'}   # fictional x/y only
    assert all(s['coordinate_system'] == 'synthetic_local_grid' for s in raw['sites'])


# ---- loader allowlist ----------------------------------------------------------
@pytest.mark.parametrize('bad', [
    '../../evaluation/ground_truth/demo/DEMO-005.json',
    'demo/../../../evaluation/ground_truth/demo/DEMO-005.json',
    '..\\..\\raw\\synthetic\\demo\\DEMO-005.json',
    '/etc/passwd', 'C:/Windows/win.ini',
    'DEMO-005.json',                      # wrong depth
    'demo/DEMO-005.txt', 'demo/missing.json', 'ground_truth/demo/DEMO-005.json',
    'demo', '',
])
def test_loader_rejects_paths_outside_allowlist(bad):
    with pytest.raises(LoaderError):
        load_case(bad)


def test_loader_rejects_absolute_truth_and_raw_files():
    for p in [DATA / 'evaluation/ground_truth/demo/DEMO-005.json',
              DATA / 'raw/synthetic/demo/DEMO-005.json',
              DATA / 'processed/context/districts.csv',
              DATA / 'file_manifest.csv']:
        with pytest.raises(LoaderError):
            load_case(p)


def test_loader_accepts_relative_and_absolute_approved_path():
    a = load_case('demo/DEMO-005.json')
    b = load_case(DATA / 'processed/agent_inputs/demo/DEMO-005.json')
    assert a == b and a.scenario_id == 'DEMO-005'


def test_loader_validates_schema(tmp_path):
    (tmp_path / 'demo').mkdir()
    good = json.loads((DATA / 'processed/agent_inputs/demo/DEMO-005.json').read_text(encoding='utf-8'))
    good['unexpected'] = 1
    (tmp_path / 'demo' / 'DEMO-005.json').write_text(json.dumps(good))
    with pytest.raises(ValueError):
        CaseLoader(tmp_path).load_case('demo/DEMO-005.json')


def test_find_rejects_bad_ids():
    for bad in ('../DEMO-005', 'DEMO-005/..', 'NOPE-1', 'a b'):
        with pytest.raises(LoaderError):
            loader.find(bad)
    with pytest.raises(LoaderError):
        EvaluatorLoader().load('../DEMO-005')


# ---- runtime isolation ---------------------------------------------------------
def test_agent_facing_packages_never_reach_truth_or_simulator():
    pattern = re.compile(r'ground_truth|raw/synthetic|project\.data\.evaluator|project\.simulation|'
                         r'from\s+\.+\s*evaluator|from\s+project\.data\s+import\s+evaluator|from\s+project\s+import\s+simulation')
    offenders = []
    for pkg in ('agents', 'core', 'llm'):
        for f in (REPO_ROOT / 'project' / pkg).rglob('*.py'):
            if pattern.search(f.read_text(encoding='utf-8')):
                offenders.append(str(f.relative_to(REPO_ROOT)))
    assert offenders == []
    assert 'evaluator' not in (REPO_ROOT / 'project/data/loader.py').read_text(encoding='utf-8').split('"""', 2)[2]


# ---- provenance ----------------------------------------------------------------
def test_manifest_checksums_match():
    rows = list(csv.DictReader((DATA / 'file_manifest.csv').open(encoding='utf-8')))
    assert len(rows) == 201
    text_suffix = {'.json', '.csv', '.md', '.txt', '.geojson', '.py'}
    for row in rows:
        path = DATA / row['path'] if (DATA / row['path']).exists() else REPO_ROOT / row['path']
        content = path.read_bytes()
        accepted = {hashlib.sha256(content).hexdigest()}
        if path.suffix in text_suffix:         # Git may normalise line endings per platform
            lf = content.replace(b'\r\n', b'\n')
            accepted |= {hashlib.sha256(lf).hexdigest(), hashlib.sha256(lf.replace(b'\n', b'\r\n')).hexdigest()}
        assert row['sha256'] in accepted, row['path']


def test_geographic_provenance_and_attribution_retained():
    meta = (DATA / 'raw/geoboundaries/metadata.json').read_text(encoding='utf-8')
    assert '2017' in meta and 'ODbL' in meta or 'Open Data Commons Open Database' in meta
    for name in ('download_manifest.json', 'CITATION-AND-USE-geoBoundaries.txt', 'lka_adm2_simplified.geojson'):
        assert (DATA / 'raw/geoboundaries' / name).is_file()
    attribution = (DATA / 'ATTRIBUTION.md').read_text(encoding='utf-8')
    assert 'ODbL' in attribution and 'OpenStreetMap' in attribution
    report = json.loads((DATA / 'quality_report.json').read_text(encoding='utf-8'))
    assert report['split_counts'] == {'candidate_evaluation': 20, 'demo': 1, 'development': 10}
    assert any('UNREVIEWED' in w.upper() or 'unreviewed' in w for w in report['warnings'])
