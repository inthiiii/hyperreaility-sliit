"""Evaluator-only review packets and hash-bound, self-reported human attestations.

No model calls, model outcomes, automatic human signatures or held-out claims.
Never expose this module or its packets to agent-facing tools.
"""
import argparse
import csv
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from project.agents.extraction import template_facts
from project.core.state import build_verified_state, digest
from project.data.audit import audit
from project.data.loader import CaseLoader
from project.data.evaluator import EvaluatorLoader

FIELDS = ['scenario_id','input_sha256','truth_sha256','reviewer','reviewed_at_utc',
          'is_case_author','was_prompt_tuner','used_for_tuning','topology_resources_review',
          'report_semantics_review','labels_outcomes_review','diversity_action','decision','notes']
CHECKS = ('topology_resources_review','report_semantics_review','labels_outcomes_review')


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def topology(s):
    """ID-independent shape descriptors; similarity warnings, not isomorphism proof."""
    children=Counter(link.parent for link in s.links)
    parents={link.child:link.parent for link in s.links}
    def depth(sid):
        count=0
        while sid!=s.core_id:
            sid=parents[sid];count+=1
        return count
    depths=Counter(depth(site.site_id) for site in s.sites)
    return {'sites':len(s.sites),'root_children':children[s.core_id],
            'depth_counts':{str(k):v for k,v in sorted(depths.items())},
            'non_root_branch_degrees':sorted(v for k,v in children.items() if k!=s.core_id),
            'roads_all_depot_spokes':all(r.origin==s.depot_id for r in s.roads)}


def build_packet(root):
    root=Path(root).resolve()
    structural=audit(root,allow_unparsed_labels=True)  # Existing truth isolation, uncertainty and literal-label checks.
    loader=CaseLoader(root/'data/processed/agent_inputs')
    evaluator=EvaluatorLoader(root/'data/evaluation/ground_truth')
    index=json.loads((root/'data/raw/synthetic/case_index.json').read_text())
    categories={row['scenario_id']:row['category'] for row in index}
    dev=[loader.load_case(p) for p in sorted((loader.root/'development').glob('*.json'))]
    dev_shapes={digest(topology(s)) for s in dev}
    dev_text={' '.join(r.text.lower().split()) for s in dev for r in s.reports}
    rows=[]
    for path in sorted((loader.root/'candidate_evaluation').glob('*.json')):
        s=loader.load_case(path);truth=evaluator.load(s.scenario_id)
        resolved=build_verified_state(s,template_facts(s))
        shape=topology(s)
        reports={r.report_id:r for r in s.reports}
        recognized={fact.evidence_ids[0] for fact in template_facts(s)}
        labels=[{**label,'mechanical_label_check':'LITERAL_MATCH' if label['report_id'] in recognized else 'UNPARSED_HUMAN_REVIEW_REQUIRED','source_type':reports[label['report_id']].source_type,
                 'text':reports[label['report_id']].text} for label in truth.expected_report_facts]
        paths={'input':path,'truth':root/'data/evaluation/ground_truth/candidate_evaluation'/path.name,
               'raw':root/'data/raw/synthetic/candidate_evaluation'/path.name}
        rows.append({'scenario_id':s.scenario_id,'category':categories[s.scenario_id],
            'files':{key:{'path':p.relative_to(root).as_posix(),'sha256':file_hash(p)} for key,p in paths.items()},
            'input_content_sha256':digest(s),'topology':shape,'topology_descriptor_matches_development':digest(shape) in dev_shapes,
            'report_count':len(s.reports),
            'exact_report_text_matches_development':sum(' '.join(r.text.lower().split()) in dev_text for r in s.reports),
            'resources':{'crews':[c.model_dump() for c in s.crews],'generators':[g.model_dump() for g in s.generators]},
            'report_labels_for_human_check':labels,'unlabelled_report_ids':sorted(set(reports)-{v['report_id'] for v in labels}),
            'expected_fixture_behavior':{'basis':'narrow public-template parser and conservative resolver, not independent gold',
                'unresolved_fields':resolved.unresolved_facts,
                'planning_eligible':not resolved.unresolved_facts},
            'missing_fact_labels':truth.missing_facts,
            'future_events_for_evaluator_review':[e.model_dump() for e in truth.future_events],
            'human_review':'PENDING'})
    if len(rows)!=20 or Counter(row['category'] for row in rows)!=Counter({categories[s.scenario_id]:2 for s in dev}):
        raise ValueError('Expected two evaluation candidates per development category, twenty total')
    return {'format_version':1,'kind':'evaluation_candidate_review_packet','human_review':'PENDING',
        'held_out_validity':'NOT_ESTABLISHED','model_calls':0,
        'automated_data_audit_sha256':digest(structural),
        'category_counts':dict(Counter(row['category'] for row in rows)),
        'diversity':{'unique_topology_descriptors':len({digest(r['topology']) for r in rows}),
            'cases_matching_development_topology_descriptor':sum(r['topology_descriptor_matches_development'] for r in rows),
            'reports_matching_development_text':sum(r['exact_report_text_matches_development'] for r in rows),
            'total_reports':sum(r['report_count'] for r in rows)},
        'required_human_work':['Vary/review topology, routes, windows, skills and resource scarcity beyond seeded numeric changes.',
            'Check each report meaning, authority, conflict, timestamps and missing evidence against labels.',
            'Check expected outcomes independently; mechanical eligibility is not an optimal recovery label.',
            'Declare authorship, prompt tuning and answer exposure; retire contaminated cases or limit claims.',
            'Revise in a new dataset version; preserve the original frozen release.'],
        'cases':rows}


def worksheet(packet):
    return [{**{key:'' for key in FIELDS},'scenario_id':r['scenario_id'],
        'input_sha256':r['files']['input']['sha256'],'truth_sha256':r['files']['truth']['sha256'],
        'decision':'PENDING'} for r in packet['cases']]


def prepare(root,output):
    packet=build_packet(root);output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    (output/'packet.json').write_text(json.dumps(packet,indent=2)+'\n')
    with (output/'reviews.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS,lineterminator='\n');writer.writeheader();writer.writerows(worksheet(packet))
    lines=['# Evaluation candidate review cards','',
        'Evaluator-only material. AI-prepared mechanical checks; every human decision remains PENDING.',
        'Do not paste this packet, truth labels or future events into the application agents or prompt-tuning sessions.',
        'Read PRIORITY_5_REVIEW.md for review, revision and release instructions.','']
    for row in packet['cases']:
        lines += [f"## {row['scenario_id']} — {row['category']}",'',
            f"Input hash: `{row['files']['input']['sha256']}`.",
            f"Truth hash: `{row['files']['truth']['sha256']}`.",
            f"Topology: {json.dumps(row['topology'],sort_keys=True)}.",
            f"Shape matches development: {row['topology_descriptor_matches_development']}; exact report wording overlap: {row['exact_report_text_matches_development']}/{row['report_count']}.",
            f"Mechanical unresolved fields: {', '.join(row['expected_fixture_behavior']['unresolved_fields']) or 'none'}. This is not a gold optimum.",
            f"Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `{row['scenario_id']}`.",
            'Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.','']
    (output/'cards.md').write_text('\n'.join(lines).rstrip()+'\n')
    return packet


def read_reviews(path):
    with Path(path).open(newline='') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=FIELDS:raise ValueError('Review CSV columns do not match the worksheet')
        rows=list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError('Malformed review CSV row')
    return rows


def review_issues(packet,rows):
    expected={r['scenario_id']:r for r in packet['cases']};seen=Counter(r.get('scenario_id') for r in rows)
    issues=[]
    if set(seen)!=set(expected) or any(n!=1 for n in seen.values()):issues.append('Require exactly one review for every candidate; no duplicates or extras')
    for row in rows:
        sid=row.get('scenario_id');case=expected.get(sid)
        if case is None:continue
        for field,kind in [('input_sha256','input'),('truth_sha256','truth')]:
            if row.get(field)!=case['files'][kind]['sha256']:issues.append(sid+': stale '+field)
        if row.get('decision')!='APPROVED':issues.append(sid+': independent human decision pending or changes required')
        reviewer=row.get('reviewer','').strip()
        if not reviewer or reviewer.casefold() in {'chatgpt','claude','codex','automated','llm','ai','chatgpt/codex','claude code'}:
            issues.append(sid+': actual human reviewer required')
        try:
            stamp=datetime.fromisoformat(row.get('reviewed_at_utc','').replace('Z','+00:00'))
            if stamp.utcoffset() is None or stamp.utcoffset().total_seconds()!=0 or stamp>datetime.now(timezone.utc):raise ValueError()
        except ValueError:issues.append(sid+': valid nonfuture UTC review timestamp required')
        for field in ('is_case_author','was_prompt_tuner','used_for_tuning'):
            if row.get(field)!='NO':issues.append(sid+': '+field+' must be explicitly NO for this evaluation gate')
        if any(row.get(field)!='PASS' for field in CHECKS):issues.append(sid+': all three human checks must PASS')
        if row.get('diversity_action') not in ('REVISED','ACCEPT_LIMITATION'):
            issues.append(sid+': record revision or explicit diversity limitation')
        if len(row.get('notes','').strip())<25:issues.append(sid+': substantive rationale required (25+ characters)')
    return issues


def inspect(root,packet_dir):
    packet_dir=Path(packet_dir);saved=json.loads((packet_dir/'packet.json').read_text())
    current=build_packet(root)
    if digest(saved)!=digest(current):raise ValueError('Packet/data drift; create a new packet and repeat affected human review')
    rows=read_reviews(packet_dir/'reviews.csv');issues=review_issues(current,rows)
    return {'status':'BLOCKED' if issues else 'HUMAN_ATTESTATIONS_COMPLETE',
            'case_count':len(current['cases']),'issues':issues,'packet_sha256':digest(current),
            'independence':'Self-reported human declarations; software cannot verify independence',
            'held_out_validity':'NOT_ESTABLISHED_BY_SOFTWARE'},current,rows


def release(root,packet_dir,output):
    result,packet,rows=inspect(root,packet_dir)
    if result['issues']:raise ValueError('Review gate blocked; complete independent human review before release')
    payload={'format_version':1,'kind':'human_attested_candidate_review_release',
        'status':'HUMAN_ATTESTATIONS_COMPLETE','created_at_utc':datetime.now(timezone.utc).isoformat(),
        'independence':result['independence'],'held_out_validity':result['held_out_validity'],
        'packet_sha256':digest(packet),'reviews_sha256':digest(rows),'packet':packet,'reviews':rows}
    envelope={'payload':payload,'sha256':digest(payload)}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f:json.dump(envelope,f,indent=2);f.write('\n')
    return envelope


def validate_release(root,path,cases):
    envelope=json.loads(Path(path).read_text());payload=envelope['payload']
    if envelope['sha256']!=digest(payload) or payload.get('format_version')!=1 or payload.get('kind')!='human_attested_candidate_review_release' or payload.get('status')!='HUMAN_ATTESTATIONS_COMPLETE':
        raise ValueError('Invalid review release envelope')
    current=build_packet(root)
    if payload['packet_sha256']!=digest(current) or digest(payload['packet'])!=digest(current) or payload['reviews_sha256']!=digest(payload['reviews']):
        raise ValueError('Review release/data drift')
    if review_issues(current,payload['reviews']):raise ValueError('Review release contains incomplete or invalid human attestations')
    approved={r['scenario_id']:r for r in current['cases']}
    for case in cases:
        if case.scenario_id not in approved or approved[case.scenario_id]['input_content_sha256']!=digest(case):
            raise ValueError('Selected evaluation input is not bound to this reviewed release')
    return {'status':'HUMAN_ATTESTATIONS_COMPLETE','release_sha256':envelope['sha256'],
        'packet_sha256':digest(current),'selected_case_ids':[c.scenario_id for c in cases],
        'independence':'Self-reported; not independently verified by software',
        'held_out_validity':'NOT_ESTABLISHED_BY_SOFTWARE'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','check','release'])
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--packet',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.action=='prepare':
        packet=prepare(args.root,args.packet)
        print(json.dumps({'status':'PENDING_HUMAN_REVIEW','cases':len(packet['cases']),'diversity':packet['diversity'],'model_calls':0},indent=2));return 0
    if args.action=='check':
        result,_,_=inspect(args.root,args.packet);print(json.dumps(result,indent=2));return 2 if result['issues'] else 0
    if args.output is None:parser.error('release requires --output')
    release(args.root,args.packet,args.output);print('Created immutable human-attested candidate review release');return 0


if __name__=='__main__':raise SystemExit(main())
