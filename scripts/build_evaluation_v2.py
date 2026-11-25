"""Create a new AI-authored evaluation revision without touching the frozen starter.

These are development-visible synthetic candidates, not independently held-out data.
"""
import argparse
import copy
import json
from pathlib import Path
import random

from scripts.generate_scenarios import case,CATEGORIES
from scripts import prepare_data

ROOT=Path(__file__).resolve().parents[1]


def revised_case(index):
    category=CATEGORIES[index//2];variation=index%2
    ident=f'EVAL2-{index+1:03}';n=15+index%6;seed=55001+index;rng=random.Random(seed)
    obj=case(ident,category,seed,n);s=obj['agent_input'];truth=obj['evaluation_truth']
    ids=[site['site_id'] for site in s['sites']];depth=3+index%7
    for j,link in enumerate(s['links'],1):
        parent=j-1 if j<=depth else rng.randrange(j)
        link['parent']='CORE' if parent==0 else ids[parent-1]
    # Connected road chain with selected spokes and cross-links, rather than all depot spokes.
    edges=[];seen=set()
    def road(a,b,t):
        key=tuple(sorted((a,b)))
        if key not in seen:seen.add(key);edges.append({'road_id':f'R{len(edges)+1:02}','from':a,'to':b,'travel_minutes':t})
    previous='DEPOT'
    for sid in ids:road(previous,sid,5);previous=sid
    isolated_leaf=category=='route_closure' and variation==0
    for j in range(3,n,4):
        if isolated_leaf and ids[j]==ids[-1]:continue
        road('DEPOT',ids[j],10+5*(j%3))
    for j in range(0,n-3,4):road(ids[j],ids[j+2],10)
    if category=='route_closure' and variation==1:road(ids[-1],ids[-4],10)
    s['roads']=edges
    critical=ids[depth-1] if variation==0 else ids[-1]
    target=ids[max(0,depth//2-1)] if variation==0 else ids[-1]
    if category=='route_closure':target=ids[-1]
    if category=='resource_loss_replanning':target=ids[0]
    for service in s['services']:
        service['critical']=service['site_id']==critical
        service['weight']=5 if service['critical'] else 1
        service['label']='Synthetic emergency facility' if service['critical'] else 'Synthetic community service'
    s['crews']=[{'crew_id':f'C{i+1}','location':'DEPOT' if i<2 else ids[2],
        'available_from_min':0 if i<2 else 15,'available_until_min':720 if i%2 else 480+30*(index%4),
        'skills':['equipment','generator'] if i==0 else ['equipment','backhaul','generator']}
        for i in range(2+index%3)]
    if category=='skill_shortage':
        for crew in s['crews']:crew['skills']=[v for v in crew['skills'] if v!='backhaul']
    if category=='resource_loss_replanning':
        for crew in s['crews'][:2]:crew['available_from_min']=0;crew['available_until_min']=720
    s['generators']=[{'generator_id':f'G{i+1}','location':'DEPOT' if i==0 else ids[2],
        'available':i==0,'autonomy_minutes':(60+30*variation if category=='generator_exhaustion' else 90+30*((index+i)%5)),
        'deployment_minutes':10+5*((index+i)%2),'max_deployments':1}
        for i in range(1+index%2)]
    truth_sites={sid:{'equipment_ok':True,'grid_power_ok':True} for sid in ids}
    truth_links={link['link_id']:True for link in s['links']}
    truth_roads={road['road_id']:True for road in edges}
    link_for={link['child']:link['link_id'] for link in s['links']}
    if category in ('equipment_only','route_closure','conflicting_reports','missing_critical_evidence','resource_loss_replanning'):
        truth_sites[target]['equipment_ok']=False
    if category in ('power_only','generator_exhaustion'):truth_sites[critical]['grid_power_ok']=False
    if category in ('power_and_backhaul','skill_shortage'):
        truth_sites[ids[0]]['grid_power_ok']=False
        truth_sites[critical]['grid_power_ok']=False
        truth_links[link_for[critical]]=False
    if category=='resource_loss_replanning':truth_sites[critical]['grid_power_ok']=False
    closed=None
    if category=='route_closure':
        closed=next(r['road_id'] for r in edges if r['to']==target and r['from']==ids[-2])
        truth_roads[closed]=False
    observed_sites=copy.deepcopy(truth_sites);observed_links=dict(truth_links);observed_roads=dict(truth_roads)
    reports=[];labels=[]
    def report(typ,sid,attr,value,source='authoritative_snapshot',when=0,resolution='verified'):
        rid=f'V2-{index+1:02}-OBS-{len(reports)+1:02}'
        meanings={('equipment_ok',False):'the site equipment is not functioning and needs repair',
                  ('equipment_ok',True):'the site equipment is functioning normally',
                  ('grid_power_ok',False):'the mains supply is absent at this site',
                  ('grid_power_ok',True):'the mains supply is present at this site',
                  ('backhaul_ok',False):'the backhaul circuit is broken',
                  ('backhaul_ok',True):'the backhaul circuit is carrying traffic',
                  ('open',False):'the access connection is blocked to all crews',
                  ('open',True):'the access connection is passable to crews'}
        text=f'Inspection {index+1:02}/{len(reports)+1:02} records {sid}: {meanings[attr,value]}.'
        reports.append({'report_id':rid,'source_type':source,'observed_at_min':when,
                        'received_at_min':max(0,when),'text':text})
        labels.append({'report_id':rid,'target_type':typ,'target_id':sid,'attribute':attr,
                       'reported_value':value,'expected_resolution':resolution})
    for sid,values in truth_sites.items():
        for attr,value in values.items():
            if value is False:
                observed_sites[sid][attr]=None
                if category!='missing_critical_evidence':report('site',sid,attr,value)
    for lid,value in truth_links.items():
        if not value:observed_links[lid]=None;report('link',lid,'backhaul_ok',False)
    for rid,value in truth_roads.items():
        if not value:observed_roads[rid]=None;report('road',rid,'open',False)
    if category=='conflicting_reports':
        labels[0]['expected_resolution']='conflict_requires_confirmation'
        report('site',target,'equipment_ok',True,when=5,resolution='conflict_requires_confirmation')
        for r in reports:r['received_at_min']=5
    if category=='stale_reports':
        observed_sites[target]['equipment_ok']=None
        report('site',target,'equipment_ok',False,'unverified_message',-45,'stale_not_authoritative')
        report('site',target,'equipment_ok',True)
    if category=='missing_critical_evidence' and variation:
        report('site',target,'grid_power_ok',True)
    s['observed_state']={'sites':observed_sites,'links':observed_links,'roads':observed_roads}
    s['reports']=reports;s['current_time_min']=5 if category=='conflicting_reports' else 0
    s['region_label']='AI-authored synthetic evaluation revision v2; no real network assets'
    actions=[]
    for sid in ids:
        actions.append({'action_id':'EQ-'+sid,'kind':'equipment_repair','target_id':sid,'location':sid,
            'duration_minutes':90 if category=='resource_loss_replanning' and sid==target else 25+5*rng.randrange(12),'required_skill':'equipment'})
    for link in s['links']:
        actions.append({'action_id':'BH-'+link['link_id'],'kind':'link_repair','target_id':link['link_id'],
            'location':link['child'],'duration_minutes':30+5*rng.randrange(12),'required_skill':'backhaul'})
    for gen in s['generators']:
        for sid in ids:actions.append({'action_id':f"GEN-{gen['generator_id']}-{sid}",'kind':'generator_deploy',
            'target_id':sid,'location':sid,'duration_minutes':gen['deployment_minutes'],
            'required_skill':'generator','generator_id':gen['generator_id']})
    s['action_options']=actions
    events=[]
    if category=='resource_loss_replanning':
        at=45+20*variation
        events=[{'event_id':f'V2-LOSS-{index+1}','at_min':at,
            'operator_report':{'report_id':f'V2-LOSS-OBS-{index+1}','source_type':'confirmed_field_update',
                'observed_at_min':at,'text':f'Crew C2 is unavailable for the rest of the incident from minute {at}.'},
            'truth_patch':{'crew_id':'C2','available_until_min':at}}]
    truth.update(scenario_id=ident,sites=truth_sites,links=truth_links,roads=truth_roads,
        crews=copy.deepcopy(s['crews']),generators=copy.deepcopy(s['generators']),expected_report_facts=labels,
        missing_facts=([{'target_type':'site','target_id':target,'attribute':'equipment_ok','expected_resolution':'clarification_required'}]
                       if category=='missing_critical_evidence' else []),future_events=events,
        evaluation_notes=['AI-authored and AI-reviewed engineering revision; not independent human validation.',
            'No optimal schedule, model-performance benefit or real operator outcome is claimed.'])
    obj['metadata'].update(scenario_id=ident,seed=seed,intended_split='candidate_evaluation',
        review_status='AI_REVIEW_REQUIRED',split_status='AI_AUTHORED_NOT_INDEPENDENTLY_HELD_OUT')
    return obj,{'scenario_id':ident,'category':category,'variation':variation,'target_site':target,
                'critical_site':critical,'closed_road':closed,'topology_seed':seed}


def build(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    raw=output/'data/raw/synthetic';raw.mkdir(parents=True)
    index=[]
    for split in ('demo','development'):
        for source in sorted((ROOT/'data/raw/synthetic'/split).glob('*.json')):
            obj=json.loads(source.read_text());target=raw/split/source.name;target.parent.mkdir(exist_ok=True)
            target.write_bytes(source.read_bytes());index.append(obj['metadata'])
    blueprints=[]
    for i in range(20):
        obj,blueprint=revised_case(i);p=raw/'candidate_evaluation'/(obj['metadata']['scenario_id']+'.json')
        p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(obj,indent=2)+'\n')
        index.append(obj['metadata']);blueprints.append(blueprint)
    (raw/'case_index.json').write_text(json.dumps(index,indent=2)+'\n')
    previous=prepare_data.ROOT
    try:prepare_data.ROOT=output;prepare_data.prepare()
    finally:prepare_data.ROOT=previous
    (output/'BLUEPRINT.json').write_text(json.dumps({'version':2,'authorship':'ChatGPT/Codex in Ihthisham session',
        'independent_review':False,'human_review':'PENDING','used_for_runtime_prompt_tuning':False,
        'retired_candidates':[f'EVAL-{i:03}' for i in range(1,21)],'cases':blueprints},indent=2)+'\n')
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    build(parser.parse_args().output)
