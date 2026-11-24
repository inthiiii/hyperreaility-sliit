"""Offline plumbing acceptance over the published pack; not an inference benchmark."""
import argparse
import json
from pathlib import Path

from project.core.coordinator import Coordinator
from project.core.integration import CoreSession
from project.data.audit import audit
from project.data.loader import CaseLoader
from project.data.evaluator import EvaluatorLoader
from project.simulation.episode import IncidentEpisode


def run(root):
    audit(root)
    loader=CaseLoader(root/'data/processed/agent_inputs');truths=EvaluatorLoader(root/'data/evaluation/ground_truth')
    rows=[]
    for sid in loader.case_ids():
        scenario=loader.load_case(loader.find(sid));episode=None;core=CoreSession();attempts=0
        while True:
            outcome=core.prepare(Coordinator(),scenario,'template');attempts+=1
            if outcome.model_usage:raise AssertionError('Offline delivery check made model calls')
            if outcome.status=='escalated':
                rows.append({'scenario_id':sid,'status':'escalated','reasons':outcome.reasons,'model_calls':0})
                break
            core.approve('Automated acceptance test operator')
            if episode is None:episode=IncidentEpisode(scenario,truths.load(sid))
            result=episode.advance(scenario,outcome.plan,core.approval,state=outcome.state)
            if not episode.paused:
                rows.append({'scenario_id':sid,'status':'completed','approved_episodes':attempts,
                             'metrics':result.metrics,'model_calls':0})
                break
            if attempts>=5:raise AssertionError('Unexpected incident continuation loop')
            scenario=episode.checkpoint()
    return {'check':'offline_template_delivery_acceptance','benchmark_claim':False,
            'operator':'automated test identity; not a real human approval',
            'model_calls':0,'case_count':len(rows),'cases':rows}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    result=run(root);args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print('PASS:',len(result['cases']),'cases; completed',sum(r['status']=='completed' for r in result['cases']),
          '; escalated',sum(r['status']=='escalated' for r in result['cases']),'; 0 model calls')
