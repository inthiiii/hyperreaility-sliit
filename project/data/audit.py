"""Evaluator-side data release audit and immutable candidate snapshot.

This checks mechanics and labels, not held-out independence or operator validity.
Never import this module into agents or make it a model filesystem tool.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from project.agents.extraction import template_facts
from project.core.state import digest
from project.data.loader import CaseLoader
from project.data.evaluator import EvaluatorLoader
from project.simulation.engine import _check_truth


def audit(root):
    root=Path(root).resolve()
    cases=CaseLoader(root/'data/processed/agent_inputs')
    truths=EvaluatorLoader(root/'data/evaluation/ground_truth')
    rows=[]
    for sid in cases.case_ids():
        path=cases.find(sid);scenario=cases.load_case(path);truth=truths.load(sid)
        _check_truth(scenario,truth)
        raw=json.loads((root/'data/raw/synthetic'/path.parent.name/(sid+'.json')).read_text())
        if scenario.observed_state.model_dump() != raw['agent_input']['observed_state']:
            raise ValueError(sid+': uncertainty changed during preprocessing')
        original=raw['agent_input']['reports']
        normalized=[{**r,'report_id':r['report_id'].strip(),'text':' '.join(r['text'].split())} for r in original]
        normalized.sort(key=lambda r:(r['received_at_min'],r['observed_at_min'],r['report_id']))
        if [r.model_dump() for r in scenario.reports] != normalized:
            raise ValueError(sid+': source evidence changed')
        facts={f.evidence_ids[0]:f for f in template_facts(scenario)}
        for label in truth.expected_report_facts:
            fact=facts.get(label['report_id'])
            if fact is None or (fact.target_type,fact.target_id,fact.attribute,fact.value)!=(
                    label['target_type'],label['target_id'],label['attribute'],label['reported_value']):
                raise ValueError(sid+': report fact label disagrees with literal report')
        visible=scenario.model_dump(mode='json')
        def keys(value):
            if isinstance(value,dict):
                for k,v in value.items():yield k;yield from keys(v)
            elif isinstance(value,list):
                for v in value:yield from keys(v)
        if set(keys(visible)) & {'evaluation_truth','expected_report_facts','future_events','truth_patch','evaluation_notes'}:
            raise ValueError(sid+': evaluator answers leaked into input')
        rows.append({'scenario_id':sid,'split':path.parent.name,
            'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'truth_sha256':digest(truth), 'sites':len(scenario.sites),
            'topology_hash':digest([(l.parent,l.child) for l in scenario.links]),
            'resource_hash':digest({'crews':[c.model_dump() for c in scenario.crews],
                                    'generators':[g.model_dump() for g in scenario.generators]}),
            'future_event_count':len(truth.future_events),'report_labels_checked':len(truth.expected_report_facts)})
    return {'format_version':1,'audit_kind':'automated_structural_and_literal_label_review',
            'human_review':'PENDING','held_out_validity':'NOT_ESTABLISHED',
            'limitations':['Mechanism fixtures are not real operator incidents.',
                'Candidate cases share a generator template; independent review must vary topology, resource constraints and report wording.',
                'No inference benchmark or optimal recovery result is established by this audit.'],
            'case_count':len(rows),'cases':rows}


def freeze(root,output):
    root=Path(root).resolve();report=audit(root)
    entries=[]
    for row in csv.DictReader((root/'data/file_manifest.csv').open(encoding='utf-8')):
        path=root/row['path'];content=path.read_bytes();sha=hashlib.sha256(content).hexdigest()
        if sha!=row['sha256'] or len(content)!=int(row['bytes']):
            raise ValueError('Manifest mismatch: '+row['path'])
        entries.append({'path':row['path'],'bytes':len(content),'sha256':sha})
    payload={'format_version':1,'release':'starter-candidates-2026-11-24',
             'status':'FROZEN_CANDIDATE_SNAPSHOT_NOT_VALIDATED_HELD_OUT',
             'human_review':'PENDING','automated_audit_sha256':digest(report),'files':entries}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:json.dump(payload,stream,indent=2);stream.write('\n')
    return payload


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--freeze',action='store_true')
    args=parser.parse_args()
    if args.freeze:payload=freeze(args.root,args.output)
    else:
        payload=audit(args.root);args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x',encoding='utf-8') as stream:json.dump(payload,stream,indent=2);stream.write('\n')
    print('PASS:',payload.get('case_count',len(payload.get('files',[]))),'records; human review remains pending')

if __name__=='__main__':main()
