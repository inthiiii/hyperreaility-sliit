#!/usr/bin/env python3
"""Independent structural and edge-case checks, not benchmark validation."""
import json
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def read(p): return json.loads(p.read_text())
def check(condition, message):
    if not condition: raise ValueError(message)
def main():
    index = read(ROOT/'data/evaluation/case_index.json')
    check(Counter(m['intended_split'] for m in index) == {'demo':1,'development':10,'candidate_evaluation':20}, 'Wrong case counts')
    check(len({m['scenario_id'] for m in index}) == 31, 'Duplicate case IDs')
    for m in index:
        sid, split, category = m['scenario_id'], m['intended_split'], m['category']
        x = read(ROOT/'data/processed/agent_inputs'/split/(sid+'.json'))
        truth = read(ROOT/'data/evaluation/ground_truth'/split/(sid+'.json'))
        raw = read(ROOT/'data/raw/synthetic'/split/(sid+'.json'))
        check(x['observed_state'] == raw['agent_input']['observed_state'], sid+': changed unknown observations')
        def keys(obj):
            if isinstance(obj,dict):
                for k,v in obj.items(): yield k; yield from keys(v)
            elif isinstance(obj,list):
                for v in obj: yield from keys(v)
        check(not set(keys(x)) & {'evaluation_truth','expected_report_facts','future_events','truth_patch','category','seed'}, sid+': hidden answers leaked')
        sites = {s['site_id'] for s in x['sites']}
        links = {l['link_id'] for l in x['links']}
        check(len(sites)==len(x['sites']),sid+': duplicate sites')
        check(len(sites)==5 if split=='demo' else 15<=len(sites)<=20,sid+': site size')
        check(len(x['crews'])==2 and len(x['generators'])==1,sid+': resources')
        parents = {}
        for l in x['links']:
            check(l['child'] in sites and l['parent'] in sites|{'CORE'},sid+': link reference')
            check(l['child'] not in parents,sid+': multiple parents in tree fixture')
            parents[l['child']]=l['parent']
        for site in sites:
            cursor, visited = site,set()
            while cursor!='CORE':
                check(cursor not in visited and cursor in parents,sid+': cyclic/disconnected backhaul')
                visited.add(cursor);cursor=parents[cursor]
        for s in x['services']: check(s['site_id'] in sites and s['weight']>0,sid+': invalid service')
        for r in x['roads']:
            check(r['from'] in sites|{'DEPOT'} and r['to'] in sites|{'DEPOT'},sid+': road reference')
            check(r['travel_minutes']>0 and r['travel_minutes']%5==0,sid+': travel unit')
        for a in x['action_options']:
            check(a['location'] in sites,sid+': action location')
            check(a['target_id'] in (links if a['kind']=='link_repair' else sites),sid+': action target')
            check(a['duration_minutes']>0 and a['duration_minutes']%5==0,sid+': action unit')
        reports={r['report_id']:r for r in x['reports']}
        check(len(reports)==len(x['reports']),sid+': duplicate report')
        for r in reports.values(): check(r['observed_at_min']<=r['received_at_min']<=x['current_time_min'],sid+': report from future')
        for f in truth['expected_report_facts']: check(f['report_id'] in reports,sid+': label evidence missing')
        if category=='conflicting_reports': check(len(reports)==2,sid+': conflict lost')
        if category=='stale_reports': check(any(r['observed_at_min']<0 for r in reports.values()),sid+': stale report lost')
        if category=='missing_critical_evidence':
            check(x['observed_state']['sites']['S01']['equipment_ok'] is None and len(reports)==0,sid+': unknown erased')
        if category=='resource_loss_replanning': check(len(truth['future_events'])==1,sid+': event missing')
    geo=read(ROOT/'data/processed/context/lka_districts.geojson')
    check(len(geo['features'])==25,'Wrong district count')
    check(len(read(ROOT/'data/processed/context/western_district_context.geojson')['features'])==3,'Western subset')
    # Hand-calculated five-site dependency example: gen at S02 restores S02 and S04 only.
    d=read(ROOT/'data/processed/agent_inputs/demo/DEMO-005.json')
    t=read(ROOT/'data/evaluation/ground_truth/demo/DEMO-005.json')
    parent={l['child']:(l['parent'],l['link_id']) for l in d['links']}
    def available(site, powered):
        if site=='CORE': return True
        state=t['sites'][site]; p,lid=parent[site]
        return state['equipment_ok'] and (state['grid_power_ok'] or site in powered) and t['links'][lid] and available(p,powered)
    check([s['site_id'] for s in d['sites'] if available(s['site_id'],set())]==[],'Demo initial dependency')
    restored=[s['site_id'] for s in d['sites'] if available(s['site_id'],{'S02'})]
    check(restored==['S02','S04'],'Demo backhaul/power dependency')
    check(sum(s['weight'] for s in d['services'] if s['site_id'] in restored)==6,'Demo weighted availability')
    print('PASS: 31 scenario structures, references, evidence isolation and edge cases; 25 districts; hand-calculated five-site dependency checks.')
    print('Not tested: application, optimizer, LLM quality, GIS topology or held-out benchmark validity. Independent scenario review is still required.')
if __name__=='__main__': main()
