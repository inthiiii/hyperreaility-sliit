"""Evaluator-only AI-authored/self-reviewed revision checks; never human sign-off.

Reference schedules are simple mechanism oracles, not model benchmarks or optima.
"""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import heapq
import json
from pathlib import Path
import re

from project.core.coordinator import approve
from project.core.schemas import EvidenceFact,Plan,ScheduledAction
from project.core.state import AUTHORITY,build_verified_state,digest
from project.data.loader import CaseLoader
from project.data.evaluator import EvaluatorLoader
from project.simulation.episode import IncidentEpisode
from project.simulation.engine import SimulationRejected
from project.evaluation.case_review import build_packet,file_hash,prepare

FIELDS=['scenario_id','input_sha256','truth_sha256','reviewer','reviewer_kind','independent_review',
        'is_case_author','was_prompt_tuner','used_for_runtime_prompt_tuning','human_review',
        'reviewed_at_utc','topology_resources_review','report_semantics_review','labels_outcomes_review','decision','notes']
MEANINGS={
 'the site equipment is not functioning and needs repair':('site','equipment_ok',False),
 'the site equipment is functioning normally':('site','equipment_ok',True),
 'the mains supply is absent at this site':('site','grid_power_ok',False),
 'the mains supply is present at this site':('site','grid_power_ok',True),
 'the backhaul circuit is broken':('link','backhaul_ok',False),
 'the backhaul circuit is carrying traffic':('link','backhaul_ok',True),
 'the access connection is blocked to all crews':('road','open',False),
 'the access connection is passable to crews':('road','open',True)}


def check(condition,message):
    if not condition:raise ValueError(message)


def labelled_facts(s,t):
    reports={r.report_id:r for r in s.reports};facts=[]
    check(len(t.expected_report_facts)==len(reports),'Every v2 report needs an explicit checked claim label')
    check(len({r['report_id'] for r in t.expected_report_facts})==len(reports),'Duplicate report label')
    for label in t.expected_report_facts:
        r=reports[label['report_id']]
        match=re.fullmatch(r'Inspection [0-9]+/[0-9]+ records ([A-Za-z0-9_-]+): (.+)\.',r.text)
        check(match is not None and match[2] in MEANINGS,'Unrecognized v2 wording requires renewed semantic review')
        typ,attr,value=MEANINGS[match[2]]
        check((typ,match[1],attr,value)==(label['target_type'],label['target_id'],label['attribute'],label['reported_value']),
              'Report meaning contradicts its declared label')
        facts.append(EvidenceFact(target_type=typ,target_id=match[1],attribute=attr,value=value,
            evidence_ids=[r.report_id],observed_at_min=r.observed_at_min,received_at_min=r.received_at_min,
            status='verified' if r.source_type in AUTHORITY else 'unverified',
            reason='AI review reference claim, not runtime extraction or independent human gold'))
    return facts


def available(s,t,*,fixed_site=None,powered_site=None):
    # Deliberately separate path-walk arithmetic; no planner/forecast/simulator helper.
    parents={link.child:(link.parent,link.link_id) for link in s.links};online=[]
    for service in s.services:
        sid=service.site_id;ok=True
        while sid!=s.core_id:
            parent,lid=parents[sid];v=t.sites[sid]
            ok=ok and (v.equipment_ok or sid==fixed_site) and (v.grid_power_ok or sid==powered_site) and t.links[lid]
            sid=parent
        if ok:online.append(service.service_id)
    return set(online)


def route(s,roads,origin,target):
    graph={sid:[] for sid in [s.depot_id,*[v.site_id for v in s.sites]]}
    for road in s.roads:
        if roads[road.road_id]:
            graph[road.origin].append((road.to,road.travel_minutes));graph[road.to].append((road.origin,road.travel_minutes))
    queue=[(0,origin,[origin])];seen=set()
    while queue:
        minutes,node,path=heapq.heappop(queue)
        if node in seen:continue
        seen.add(node)
        if node==target:return path,minutes
        for neighbor,cost in graph[node]:
            if neighbor not in seen:heapq.heappush(queue,(minutes+cost,neighbor,path+[neighbor]))
    return None


def fixture_plan(s,state,actions,version):
    return Plan(plan_id=f'AI-REVIEW-{s.scenario_id}-{version}',scenario_id=s.scenario_id,state_version=state.state_version,
        state_hash=digest(state),actions=actions,unmet_needs=[],evidence_ids=[s.policy.evidence_id],
        planner_config={'purpose':'curated mechanism reference; not an agent plan or optimum'},
        explanation='Automated evaluator fixture; not a human or production dispatch')


def run_reference(s,t,actions):
    episode=IncidentEpisode(s,t);current=s;version=1;stale_rejected=True
    while True:
        # Reference facts come only from declared visible claims, never private world fields.
        facts=labelled_facts(s,t) if version==1 else []
        state=build_verified_state(current,facts,state_version=version)
        p=fixture_plan(current,state,actions if version==1 else [],version)
        authorization=approve(p.plan_id,version,'approve',plan=p,state=state,operator_id='Automated AI-review oracle; not a human')
        result=episode.advance(current,p,authorization,state=state)
        if episode.complete:return result,version,stale_rejected
        check(episode.paused and version<3,'Unexpected reference continuation')
        checkpoint=episode.checkpoint()
        try:episode.advance(checkpoint,p,authorization,state=state)
        except SimulationRejected:pass
        else:stale_rejected=False
        current=checkpoint;version+=1


def reference_action(s,t,blueprint,*,dynamic=False):
    target=blueprint['target_site'];category=blueprint['category']
    generator=category in ('power_only','generator_exhaustion')
    if generator:target=blueprint['critical_site']
    crew=next(c for c in s.crews if c.crew_id==('C2' if dynamic else 'C1'))
    gen=s.generators[0]
    option=next(a for a in s.action_options if a.target_id==target and
                a.kind==('generator_deploy' if generator else 'equipment_repair') and
                (not generator or a.generator_id==gen.generator_id))
    found=route(s,t.roads,crew.location,target)
    if not found:return None
    path,minutes=found;departure=max(s.current_time_min,crew.available_from_min)
    return ScheduledAction(action_id=option.action_id,kind=option.kind,target_id=target,crew_id=crew.crew_id,
        generator_id=option.generator_id,departure_min=departure,travel_route=path,
        work_start_min=departure+minutes,work_end_min=departure+minutes+option.duration_minutes)


def audit_revision(root):
    root=Path(root);packet=build_packet(root)
    check(packet['diversity']['cases_matching_development_topology_descriptor']==0,'Topology overlap remains')
    check(packet['diversity']['reports_matching_development_text']==0,'Exact report-text overlap remains')
    blueprints=json.loads((root/'BLUEPRINT.json').read_text())['cases'];by_id={r['scenario_id']:r for r in blueprints}
    check(len(by_id)==20 and set(by_id)=={r['scenario_id'] for r in packet['cases']},'Blueprint coverage mismatch')
    loader=CaseLoader(root/'data/processed/agent_inputs');truths=EvaluatorLoader(root/'data/evaluation/ground_truth')
    rows=[]
    for record in packet['cases']:
        sid=record['scenario_id'];b=by_id[sid];s=loader.load_case(loader.find(sid));t=truths.load(sid)
        facts=labelled_facts(s,t);state=build_verified_state(s,facts)
        expected_unknown=[f"site:{b['target_site']}:equipment_ok"] if b['category'] in ('conflicting_reports','missing_critical_evidence') else []
        check(state.unresolved_facts==expected_unknown,sid+': wrong conservative resolution')
        if b['category']=='stale_reports':check(state.resolved_observations.sites[b['target_site']].equipment_ok is True,'Stale message overrode authority')
        if b['category']=='skill_shortage':check(all('backhaul' not in c.skills for c in s.crews),'Missing shortage')
        if b['category']=='route_closure':
            reachable=route(s,t.roads,s.depot_id,b['target_site']) is not None
            check(reachable==(b['variation']==1),'Road closure/alternate path mismatch')
        before=available(s,t);weight={v.service_id:v.weight for v in s.services}
        weighted=sum(weight[v] for v in before)*s.horizon_min
        total=sum(weight.values())*s.horizon_min
        result,episodes,stale=run_reference(s,t,[])
        check(result.metrics['weighted_available_min']==weighted and result.metrics['weighted_downtime_min']==total-weighted,
              sid+': no-work arithmetic differs from simulator')
        check(stale,'Stale approval accepted on continuation')
        mechanism={'no_work_weighted_available_min':weighted,'no_work_weighted_downtime_min':total-weighted,
                   'no_work_approved_episodes':episodes,'stale_approval_rejected':stale}
        category=b['category']
        if category in ('equipment_only','power_only','generator_exhaustion') or (category=='route_closure' and b['variation']==1):
            action=reference_action(s,t,b);check(action is not None,'Expected reference route missing')
            reference,_,_=run_reference(s,t,[action]);end=action.work_end_min
            generator=action.kind=='generator_deploy'
            after=available(s,t,powered_site=action.target_id) if generator else available(s,t,fixed_site=action.target_id)
            duration=min(s.generators[0].autonomy_minutes,s.horizon_min-end) if generator else s.horizon_min-end
            expected=weighted+sum(weight[v] for v in after-before)*duration
            check(reference.metrics['weighted_available_min']==expected,sid+': reference-action arithmetic differs')
            if generator:
                intervals=reference.run_metadata['service_availability'][next(v.service_id for v in s.services if v.site_id==action.target_id)]['intervals']
                check(intervals==[[end,end+duration]],'Generator expiry was extended or double-counted')
            mechanism.update(reference_action=action.model_dump(),reference_weighted_available_min=expected,
                             reference_scope='curated one-action mechanism oracle, not an optimal or model-produced plan')
        if category=='resource_loss_replanning':
            action=reference_action(s,t,b,dynamic=True);check(action is not None,'Crew-loss reference route missing')
            at=t.future_events[0].at_min;check(action.work_start_min<at<action.work_end_min,'Reference work does not straddle loss')
            episode=IncidentEpisode(s,t);p=fixture_plan(s,state,[action],1)
            auth=approve(p.plan_id,1,'approve',plan=p,state=state,operator_id='Automated review fixture')
            prefix=episode.advance(s,p,auth,state=state)
            check(episode.paused and prefix.metrics['weighted_downtime_min'] is None,'Crew loss did not pause/unscore prefix')
            outcome=prefix.run_metadata['action_outcomes'][action.action_id]
            check(outcome['status']=='paused' and not prefix.run_metadata['all_completed_actions'],'Unfinished repair got completion credit')
            check(prefix.metrics['weighted_available_so_far_min']==sum(weight[v] for v in before)*at,'Wrong prefix arithmetic')
            mechanism.update(crew_loss_at_min=at,unfinished_work='PAUSED_WITHOUT_COMPLETION_CREDIT',prefix_full_score=None)
        rows.append({'scenario_id':sid,'category':category,'status':'PASS','input_sha256':record['files']['input']['sha256'],
            'truth_sha256':record['files']['truth']['sha256'],'label_claims_checked':len(facts),
            'expected_unresolved_fields':expected_unknown,'topology_resources':'PASS','report_semantics':'PASS',
            'mechanism_checks':mechanism})
    return {'format_version':1,'scope':'AI-authored/self-reviewed synthetic mechanism checks; not independent validation or model benchmarking',
        'independent_review':False,'human_review':'PENDING','model_calls':0,'cases':rows,
        'diversity':packet['diversity'],'packet_sha256':digest(packet),'claims_optimality_or_model_advantage':False}


def record_review(root):
    root=Path(root);report=audit_revision(root);packet=build_packet(root)
    out=root/'review';out.mkdir(exist_ok=False)
    (out/'packet.json').write_text(json.dumps(packet,indent=2)+'\n')
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    now=datetime.now(timezone.utc).isoformat();rows=[]
    for r in report['cases']:
        mechanism=r['mechanism_checks']
        note=(f"AI-authored and self-reviewed {r['category']}; checked {r['label_claims_checked']} report claims, "
            f"unresolved fields {r['expected_unresolved_fields']}, and no-work downtime {mechanism['no_work_weighted_downtime_min']} weighted minutes. "
            +('Checked one-action arithmetic and physical timing. ' if 'reference_action' in mechanism else '')
            +('Checked partial-work pause and null prefix score. ' if 'crew_loss_at_min' in mechanism else '')
            +'Revised graph/routes/resources/wording; not independent human gold or an optimum.')
        rows.append(dict(zip(FIELDS,[r['scenario_id'],r['input_sha256'],r['truth_sha256'],
            'ChatGPT/Codex in Ihthisham session','AI','NO','YES','YES','NO','PENDING',now,
            'PASS','PASS','PASS','AI_REVIEWED',note])))
    with (out/'reviews.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS,lineterminator='\n');writer.writeheader();writer.writerows(rows)
    prepare(root,out/'human')  # Separate genuine human worksheet remains blank.
    return report


def checked_rows(root,packet):
    with (Path(root)/'review/reviews.csv').open(newline='') as f:
        reader=csv.DictReader(f);check(reader.fieldnames==FIELDS,'Wrong AI review columns');rows=list(reader)
    expected={r['scenario_id']:r for r in packet['cases']}
    check(len(rows)==20 and len({r['scenario_id'] for r in rows})==20 and {r['scenario_id'] for r in rows}==set(expected),'AI review coverage mismatch')
    for row in rows:
        record=expected[row['scenario_id']]
        check(row['input_sha256']==record['files']['input']['sha256'] and row['truth_sha256']==record['files']['truth']['sha256'],'Stale AI review hashes')
        check(row['reviewer_kind']=='AI' and row['independent_review']=='NO' and row['human_review']=='PENDING' and
              row['is_case_author']=='YES' and row['was_prompt_tuner']=='YES' and row['used_for_runtime_prompt_tuning']=='NO' and row['decision']=='AI_REVIEWED',
              'AI review cannot masquerade as independent human approval')
        check(all(row[k]=='PASS' for k in ('topology_resources_review','report_semantics_review','labels_outcomes_review')),'Incomplete AI checks')
        stamp=datetime.fromisoformat(row['reviewed_at_utc']);check(stamp.utcoffset() is not None and stamp.utcoffset().total_seconds()==0 and stamp<=datetime.now(timezone.utc),'Invalid AI review date')
        check(bool(row['reviewer'].strip()) and len(row['notes'])>=25,'Missing AI review provenance/rationale')
    return rows


def snapshot_files(root):
    root=Path(root);return sorted([p for p in (root/'data').rglob('*') if p.is_file()]+[root/'BLUEPRINT.json']+
                                [p for p in (root/'review').rglob('*') if p.is_file()])


def freeze(root,output):
    root=Path(root);packet=build_packet(root);report=audit_revision(root);rows=checked_rows(root,packet)
    check(digest(report)==digest(json.loads((root/'review/validation.json').read_text())),'Stored validation drift')
    check(digest(packet)==digest(json.loads((root/'review/packet.json').read_text())),'Stored packet drift')
    payload={'format_version':1,'kind':'ai_authored_self_reviewed_candidate_release','status':'AI_REVIEWED_FROZEN',
        'independent_review':False,'human_review':'PENDING','held_out_validity':'NOT_ESTABLISHED',
        'packet_sha256':digest(packet),'validation_sha256':digest(report),'reviews_sha256':digest(rows),
        'files':[{'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':file_hash(p)} for p in snapshot_files(root)]}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f:json.dump({'payload':payload,'sha256':digest(payload)},f,indent=2);f.write('\n')
    return payload


def validate_release(root,path,cases):
    root=Path(root).resolve();envelope=json.loads(Path(path).read_text());p=envelope['payload']
    check(envelope['sha256']==digest(p) and p.get('format_version')==1 and p.get('held_out_validity')=='NOT_ESTABLISHED' and p.get('kind')=='ai_authored_self_reviewed_candidate_release' and
          p.get('status')=='AI_REVIEWED_FROZEN' and p.get('independent_review') is False and p.get('human_review')=='PENDING',
          'Invalid AI release or false independence claim')
    expected=set()
    for entry in p['files']:
        relative=Path(entry['path']);check(not relative.is_absolute() and '..' not in relative.parts,'Unsafe release path')
        target=(root/relative).resolve();target.relative_to(root)
        check(entry['path'] not in expected,'Duplicate frozen path');expected.add(entry['path'])
        check(target.stat().st_size==entry['bytes'] and file_hash(target)==entry['sha256'],'Frozen revision changed')
    check(expected=={q.relative_to(root).as_posix() for q in snapshot_files(root)},'Frozen inventory changed')
    packet=build_packet(root);report=audit_revision(root);rows=checked_rows(root,packet)
    check(p['packet_sha256']==digest(packet) and p['validation_sha256']==digest(report) and p['reviews_sha256']==digest(rows),'Review binding drift')
    by_id={r['scenario_id']:r for r in packet['cases']}
    for case in cases:check(case.scenario_id in by_id and digest(case)==by_id[case.scenario_id]['input_content_sha256'],'Case is not bound to AI revision')
    return {'status':'AI_REVIEWED_FROZEN','release_sha256':envelope['sha256'],'packet_sha256':digest(packet),
        'selected_case_ids':[c.scenario_id for c in cases],'independent_review':False,'human_review':'PENDING',
        'held_out_validity':'NOT_ESTABLISHED','scope':'AI-assisted synthetic engineering evaluation only'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['review','freeze','validate'])
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--release',type=Path)
    args=parser.parse_args()
    if args.action=='review':result=record_review(args.root)
    elif args.action=='freeze':result=freeze(args.root,args.release or args.root/'AI_RELEASE.json')
    else:result=validate_release(args.root,args.release or args.root/'AI_RELEASE.json',[])
    print(json.dumps({'status':result.get('status','AI_REVIEWED'),'case_count':len(result.get('cases',[])) or 20,
                     'independent_review':False,'human_review':'PENDING','model_calls':0},indent=2))


if __name__=='__main__':main()
