#!/usr/bin/env python3
"""Generate provisional synthetic fixtures; never label these operator observations."""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = [
    'equipment_only', 'power_only', 'power_and_backhaul', 'skill_shortage',
    'route_closure', 'conflicting_reports', 'stale_reports',
    'missing_critical_evidence', 'generator_exhaustion', 'resource_loss_replanning'
]

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')

def case(case_id, category, seed, n=15):
    rng = random.Random(seed)
    sites = [{'site_id': f'S{i:02}', 'label': f'Fictional site {i:02}',
              'x': ((i - 1) % 5) * 10, 'y': ((i - 1) // 5) * 10,
              'coordinate_system': 'synthetic_local_grid'} for i in range(1, n + 1)]
    links = [{'link_id': f'L{i:02}', 'parent': 'CORE' if i <= 2 else ('S01' if i % 2 else 'S02'),
              'child': f'S{i:02}'} for i in range(1, n + 1)]
    roads = [{'road_id': f'R{i:02}', 'from': 'DEPOT', 'to': f'S{i:02}',
              'travel_minutes': rng.choice([5, 10, 15, 20, 25, 30])} for i in range(1, n + 1)]
    services = [{'service_id': f'V{i:02}', 'site_id': f'S{i:02}',
                 'label': 'Fictional critical facility' if i == 2 else f'Fictional service {i:02}',
                 'critical': i == 2, 'weight': 5 if i == 2 else 1,
                 'policy_evidence_id': 'POLICY-001'} for i in range(1, n + 1)]
    crews = [{'crew_id': 'C1', 'location': 'DEPOT', 'available_from_min': 0,
              'available_until_min': 720, 'skills': ['equipment', 'generator']},
             {'crew_id': 'C2', 'location': 'DEPOT', 'available_from_min': 0,
              'available_until_min': 720, 'skills': ['backhaul', 'equipment', 'generator']}]
    generators = [{'generator_id': 'G1', 'location': 'DEPOT', 'available': True,
                   'autonomy_minutes': rng.choice([120, 180, 240, 300, 360]),
                   'deployment_minutes': 15, 'max_deployments': 1}]
    truth_sites = {s['site_id']: {'equipment_ok': True, 'grid_power_ok': True} for s in sites}
    truth_links = {l['link_id']: True for l in links}
    truth_roads = {r['road_id']: True for r in roads}
    if category in ['equipment_only', 'route_closure', 'conflicting_reports', 'missing_critical_evidence']:
        truth_sites['S01']['equipment_ok'] = False
    if category in ['power_only', 'generator_exhaustion']:
        truth_sites['S02']['grid_power_ok'] = False
    if category in ['power_and_backhaul', 'skill_shortage']:
        truth_sites['S01']['grid_power_ok'] = False
        truth_sites['S02']['grid_power_ok'] = False
        truth_links['L01'] = False
    if category == 'skill_shortage':
        crews[1]['skills'] = ['equipment', 'generator']
    if category == 'route_closure':
        truth_roads['R01'] = False
    if category == 'resource_loss_replanning':
        truth_sites['S01']['equipment_ok'] = False
        truth_sites['S02']['grid_power_ok'] = False
    if category == 'generator_exhaustion':
        generators[0]['autonomy_minutes'] = 120

    observed_sites = {k: dict(v) for k, v in truth_sites.items()}
    observed_links = dict(truth_links)
    observed_roads = dict(truth_roads)
    reports, labels = [], []

    def report(target_type, target_id, attr, value, source='authoritative_snapshot', when=0, resolution='verified'):
        rid = f'REP-{len(reports) + 1:03}'
        phrases = {
            'equipment_ok': 'equipment is operational' if value else 'equipment has failed',
            'grid_power_ok': 'grid power is available' if value else 'grid power is unavailable',
            'backhaul_ok': 'backhaul link is operational' if value else 'backhaul link has failed',
            'open': 'access road is open' if value else 'access road is closed'
        }
        reports.append({'report_id': rid, 'source_type': source, 'observed_at_min': when,
                        'received_at_min': 0, 'text': f'{target_id}: {phrases[attr]}.'})
        labels.append({'target_type': target_type, 'target_id': target_id, 'attribute': attr,
                       'reported_value': value, 'report_id': rid, 'expected_resolution': resolution})
        return rid

    # Only affected/selected fields are withheld from structured observations.
    # Authoritative text reports then supply evidence for extraction.
    for sid, state in truth_sites.items():
        for attr, value in state.items():
            if value is False:
                observed_sites[sid][attr] = None
                if not (category == 'missing_critical_evidence' and sid == 'S01' and attr == 'equipment_ok'):
                    report('site', sid, attr, value)
    for lid, value in truth_links.items():
        if value is False:
            observed_links[lid] = None
            report('link', lid, 'backhaul_ok', value)
    for rid, value in truth_roads.items():
        if value is False:
            observed_roads[rid] = None
            report('road', rid, 'open', value)
    if category == 'conflicting_reports':
        labels[0]['expected_resolution'] = 'conflict_requires_confirmation'
        report('site', 'S01', 'equipment_ok', True, when=5, resolution='conflict_requires_confirmation')
        for r in reports:
            r['received_at_min'] = 5
    if category == 'stale_reports':
        observed_sites['S01']['equipment_ok'] = None
        report('site', 'S01', 'equipment_ok', False, 'unverified_message', -60, 'stale_not_authoritative')
        report('site', 'S01', 'equipment_ok', True, 'authoritative_snapshot', 0)
    missing = []
    if category == 'missing_critical_evidence':
        missing.append({'target_type': 'site', 'target_id': 'S01', 'attribute': 'equipment_ok',
                        'expected_resolution': 'clarification_required'})

    actions = []
    for s in sites:
        actions.append({'action_id': 'EQ-' + s['site_id'], 'kind': 'equipment_repair',
                        'target_id': s['site_id'], 'location': s['site_id'],
                        'duration_minutes': rng.choice([30, 45, 60, 90, 120]), 'required_skill': 'equipment'})
    for l in links:
        actions.append({'action_id': 'BH-' + l['link_id'], 'kind': 'link_repair',
                        'target_id': l['link_id'], 'location': l['child'],
                        'duration_minutes': rng.choice([30, 45, 60, 90, 120]), 'required_skill': 'backhaul'})
    for s in sites:
        actions.append({'action_id': 'GEN-G1-' + s['site_id'], 'kind': 'generator_deploy',
                        'target_id': s['site_id'], 'generator_id': 'G1', 'location': s['site_id'],
                        'duration_minutes': 15, 'required_skill': 'generator'})
    events = []
    if category == 'resource_loss_replanning':
        events.append({'event_id': 'EVT-001', 'at_min': 60,
                       'operator_report': {'report_id': 'EVENT-REP-001', 'source_type': 'confirmed_field_update',
                                           'observed_at_min': 60, 'text': 'Crew C2 is unavailable for the rest of the incident.'},
                       'truth_patch': {'crew_id': 'C2', 'available_until_min': 60}})
    start = 5 if category == 'conflicting_reports' else 0
    agent_input = {
        'schema_version': '0.1', 'scenario_id': case_id,
        'region_label': 'Fictional network in a Sri Lanka demonstration context',
        'current_time_min': start, 'horizon_min': 720,
        'core_id': 'CORE', 'depot_id': 'DEPOT', 'sites': sites, 'links': links,
        'roads': roads, 'services': services, 'crews': crews, 'generators': generators,
        'observed_state': {'sites': observed_sites, 'links': observed_links, 'roads': observed_roads},
        'action_options': actions, 'reports': reports,
        'policy': {'evidence_id': 'POLICY-001', 'approved_for_simulation': True,
                   'standard_weight': 1, 'critical_weight': 5,
                   'evidence_rule': 'Authoritative evidence must be consistent; equally authoritative conflicts require confirmation. Recency alone does not verify a fact.',
                   'max_generator_deployments_per_scenario': 1,
                   'on_crew_loss': 'Pause affected unfinished work and request operator review; preserve completed repairs.'}
    }
    truth = {'scenario_id': case_id, 'sites': truth_sites, 'links': truth_links, 'roads': truth_roads,
             'crews': crews, 'generators': generators, 'expected_report_facts': labels,
             'missing_facts': missing, 'future_events': events,
             'evaluation_notes': ['Runtime validation uses verified observations only.',
                                  'Hidden truth is for evaluation/simulation, never an agent tool.',
                                  'No optimal plan or expected improvement is claimed.']}
    return {'metadata': {'scenario_id': case_id, 'category': category, 'seed': seed,
                         'site_count': n, 'origin': 'synthetic', 'review_status': 'UNREVIEWED_DRAFT',
                         'split_status': 'candidate_only_not_frozen'},
            'agent_input': agent_input, 'evaluation_truth': truth}

def generate():
    if (ROOT / 'docs/evaluation/FROZEN_DATASET.json').exists():
        raise ValueError('Dataset release is frozen. Create a reviewed new version instead of regenerating in place.')
    out = ROOT / 'data/raw/synthetic'
    specs = []
    for split, copies, seed_base, prefix in [('development', 1, 22000, 'DEV'), ('candidate_evaluation', 2, 32000, 'EVAL')]:
        index = 0
        for category in CATEGORIES:
            for variation in range(copies):
                index += 1
                seed = seed_base + index
                n = 15 + ((index + variation) % 6)
                obj = case(f'{prefix}-{index:03}', category, seed, n)
                obj['metadata']['intended_split'] = split
                write(out / split / f'{obj["metadata"]["scenario_id"]}.json', obj)
                specs.append(obj['metadata'])
    demo = case('DEMO-005', 'power_and_backhaul', 22005, 5)
    demo['metadata']['intended_split'] = 'demo'
    write(out / 'demo/DEMO-005.json', demo)
    specs.append(demo['metadata'])
    write(out / 'case_index.json', specs)
    print('Generated 1 five-site demo, 10 development cases and 20 unreviewed evaluation candidates.')
    print('These are generated templates, not frozen held-out benchmarks; independent review is required.')

if __name__ == '__main__':
    generate()
