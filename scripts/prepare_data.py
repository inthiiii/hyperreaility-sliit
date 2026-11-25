#!/usr/bin/env python3
"""Validate/normalize raw context and split synthetic agent inputs from evaluation truth."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8', newline='\n')

def csv_rows(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(row[k], ensure_ascii=False) if isinstance(row.get(k), (list, dict)) else row.get(k, '') for k in fields})

def positions(geometry):
    def walk(x):
        if len(x) >= 2 and isinstance(x[0], (float, int)):
            yield x[:2]
        else:
            for y in x:
                yield from walk(y)
    return list(walk(geometry['coordinates']))

def prepare():
    if (ROOT / 'docs/evaluation/FROZEN_DATASET.json').exists() or (ROOT / 'AI_RELEASE.json').exists():
        raise ValueError('Dataset release is frozen. Create a reviewed new version instead of regenerating in place.')
    summary = {'context': {}, 'case_count': 0, 'split_counts': {}, 'checks': [], 'warnings': []}
    raw_geo = ROOT / 'data/raw/geoboundaries/lka_adm2_simplified.geojson'
    if raw_geo.exists():
        geo = json.loads(raw_geo.read_text())
        normalized, seen, rows = [], set(), []
        for feature in geo['features']:
            props = feature['properties']
            name = str(props['shapeName']).strip()
            ident = str(props['shapeID']).strip()
            if ident in seen:
                raise ValueError(f'Duplicate boundary ID: {ident}')
            seen.add(ident)
            if feature['geometry']['type'] not in ('Polygon', 'MultiPolygon'):
                raise ValueError('Unexpected district geometry')
            pts = positions(feature['geometry'])
            if not pts or not all(78 <= x <= 83 and 5 <= y <= 11 for x, y in pts):
                raise ValueError('Sri Lanka longitude/latitude bounds check failed')
            bbox = [min(x for x, y in pts), min(y for x, y in pts), max(x for x, y in pts), max(y for x, y in pts)]
            normalized.append({'type': 'Feature', 'properties': {'district_id': ident, 'district_name': name,
                                'source': 'geoBoundaries / OpenStreetMap / Wambacher', 'origin': 'public_geographic_context'},
                               'geometry': feature['geometry']})
            rows.append({'district_id': ident, 'district_name': name, 'min_lon': bbox[0], 'min_lat': bbox[1], 'max_lon': bbox[2], 'max_lat': bbox[3]})
        normalized.sort(key=lambda f: f['properties']['district_name'])
        write_json(ROOT / 'data/processed/context/lka_districts.geojson', {'type': 'FeatureCollection', 'features': normalized})
        western = [f for f in normalized if f['properties']['district_name'].lower().removesuffix(' district') in ('colombo', 'gampaha', 'kalutara')]
        if len(western) != 3:
            raise ValueError('Expected Colombo, Gampaha and Kalutara district names')
        write_json(ROOT / 'data/processed/context/western_district_context.geojson', {'type': 'FeatureCollection', 'features': western})
        csv_rows(ROOT / 'data/processed/context/districts.csv', sorted(rows, key=lambda r: r['district_name']), list(rows[0]))
        summary['context'] = {'districts': len(normalized), 'western_context_districts': len(western),
                              'geometry_reprojection': 'None; source longitude/latitude retained.',
                              'geometry_topology_validation': 'Not performed; add GIS validity checks if geometry is used beyond display.'}
    else:
        summary['warnings'].append('Optional geographic context not downloaded; synthetic operational cases remain usable.')
    index = json.loads((ROOT / 'data/raw/synthetic/case_index.json').read_text())
    count = Counter()
    for meta in index:
        split, ident = meta['intended_split'], meta['scenario_id']
        raw = ROOT / 'data/raw/synthetic' / split / f'{ident}.json'
        obj = json.loads(raw.read_text())
        inp, truth = obj['agent_input'], obj['evaluation_truth']
        # Keep boolean nulls: they mean unknown, not a negative observation.
        for report in inp['reports']:
            report['text'] = ' '.join(report['text'].split())
            report['report_id'] = report['report_id'].strip()
        if len({r['report_id'] for r in inp['reports']}) != len(inp['reports']):
            raise ValueError(f'{ident}: duplicate evidence identifiers')
        inp['reports'].sort(key=lambda r: (r['received_at_min'], r['observed_at_min'], r['report_id']))
        input_path = ROOT / 'data/processed/agent_inputs' / split / f'{ident}.json'
        truth_path = ROOT / 'data/evaluation/ground_truth' / split / f'{ident}.json'
        write_json(input_path, inp)
        write_json(truth_path, truth)
        if split in ['demo', 'development']:
            tables = ROOT / 'data/processed/tables' / ident
            for key, fields in [
                ('sites', ['site_id', 'label', 'x', 'y', 'coordinate_system']),
                ('links', ['link_id', 'parent', 'child']),
                ('roads', ['road_id', 'from', 'to', 'travel_minutes']),
                ('services', ['service_id', 'site_id', 'label', 'critical', 'weight', 'policy_evidence_id']),
                ('crews', ['crew_id', 'location', 'available_from_min', 'available_until_min', 'skills']),
                ('generators', ['generator_id', 'location', 'available', 'autonomy_minutes', 'deployment_minutes', 'max_deployments']),
                ('reports', ['report_id', 'source_type', 'observed_at_min', 'received_at_min', 'text']),
                ('action_options', ['action_id', 'kind', 'target_id', 'location', 'duration_minutes', 'required_skill', 'generator_id'])]:
                csv_rows(tables / f'{key}.csv', inp[key], fields)
            csv_rows(ROOT / 'data/evaluation/qa' / f'{ident}_facts.csv', truth['expected_report_facts'],
                     ['target_type', 'target_id', 'attribute', 'reported_value', 'report_id', 'expected_resolution'])
        count[split] += 1
    write_json(ROOT / 'data/evaluation/case_index.json', index)
    summary['case_count'] = len(index)
    summary['split_counts'] = dict(count)
    summary['checks'] = ['Context IDs unique and coordinate bounds checked', 'Report IDs unique; whitespace normalized',
                         'Unknown values preserved', 'Conflicting and stale reports retained',
                         'Future events and answer labels excluded from processed agent inputs']
    summary['warnings'].append('All synthetic cases are unreviewed drafts. Do not claim held-out validity, balanced difficulty or benchmark results before independent audit.')
    write_json(ROOT / 'data/quality_report.json', summary)
    rows = []
    for folder in ['data/raw', 'data/processed', 'data/evaluation']:
        for path in sorted((ROOT / folder).rglob('*')):
            if path.is_file():
                rows.append({'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size,
                             'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                             'origin': 'public_geographic_context' if 'geoboundaries' in str(path) or '/context/' in str(path) else 'synthetic'})
    csv_rows(ROOT / 'data/file_manifest.csv', rows, ['path', 'bytes', 'sha256', 'origin'])
    print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    prepare()
