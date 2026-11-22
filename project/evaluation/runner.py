"""Run paired core baselines. No simulator, restoration score, or savings is invented."""
import argparse
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import random
import time
from datetime import datetime,timezone
from project.core.coordinator import Coordinator
from project.core.schemas import ScenarioInput
from project.core.state import digest
from project.llm.client import HostedAdapter
from project.llm.health import preflight

VARIANTS={
    'heuristic':('template','greedy',True,True),
    'optimizer':('template','cp_sat',True,True),
    'single':('single','cp_sat',True,True),
    'multi':('multi','cp_sat',True,True),
    'no_reviewer':('multi','cp_sat',False,True),
    'no_feedback':('multi','cp_sat',True,False),
}
def source_hash():
    root=Path(__file__).resolve().parents[1]
    return digest({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*.py'))})

def run_benchmark(paths,output,variants=('heuristic','optimizer'),repeats=3,seed=22,allow_live=False):
    if repeats<1:raise ValueError('Repeats must be positive')
    if not variants or any(v not in VARIANTS for v in variants):raise ValueError('Unknown or empty variant list')
    if len(set(variants))!=len(variants):raise ValueError('Duplicate variants')
    cases=[ScenarioInput.model_validate_json(Path(p).read_text()) for p in paths]
    if not cases or len({c.scenario_id for c in cases})!=len(cases):raise ValueError('Provide unique visible scenario IDs')
    hosted=any(VARIANTS[v][0]!='template' for v in variants)
    if hosted and (not allow_live or preflight()['status']=='blocked'):
        raise ValueError('Hosted benchmarks require --allow-live and a configured model/key')
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    # Exclusive manifest prevents silently overwriting or mixing experiments.
    manifest={'format_version':1,'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'source_sha256':source_hash(),'cases':{c.scenario_id:digest(c) for c in cases},
        'variants':list(variants),'repeats':repeats,'order_seed':seed,
        'model_configuration':preflight() if hosted else None,
        'packages':{name:importlib.metadata.version(name) for name in ('pydantic','ortools','networkx','openai')},
        'scoring_status':'pending_independent_simulator','scope':'static visible inputs; template baselines are not LLM agents'}
    with (output/'manifest.json').open('x') as stream:json.dump(manifest,stream,indent=2)
    jobs=[(c,v,n) for c in cases for n in range(repeats) for v in variants]
    random.Random(seed).shuffle(jobs)
    rows=[]
    with (output/'attempts.jsonl').open('x') as stream:
        for case,variant,repeat in jobs:
            mode,planner,reviewer,feedback=VARIANTS[variant]
            adapter=None;started=time.monotonic()
            row={'scenario_id':case.scenario_id,'variant':variant,'repeat':repeat,
                 'status':'failed','plan_feasible':False,'model_calls':0,'actual_weighted_downtime':None,
                 'scoring_status':'pending_independent_simulator'}
            try:
                if mode!='template':adapter=HostedAdapter.from_env()
                result=Coordinator(adapter,planner=planner,reviewer_enabled=reviewer,
                    feedback_enabled=feedback,trace_dir=output/'runs').run(case,mode)
                row.update(run_id=result.run_id,status=result.status,
                    plan_feasible=bool(result.validation and result.validation.valid),
                    model_calls=len(result.model_usage),input_tokens=sum(x.get('input_tokens',0) for x in result.model_usage),
                    output_tokens=sum(x.get('output_tokens',0) for x in result.model_usage))
            except Exception as error:row['error_type']=type(error).__name__
            finally:
                if adapter:adapter.close()
            row['duration_seconds']=time.monotonic()-started
            rows.append(row);stream.write(json.dumps(row)+'\n');stream.flush()
    columns=sorted({k for row in rows for k in row})
    with (output/'attempts.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader();writer.writerows(rows)
    return rows

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenarios',nargs='+',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--variants',nargs='+',choices=list(VARIANTS),default=['heuristic','optimizer'])
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--seed',type=int,default=22)
    parser.add_argument('--allow-live',action='store_true')
    args=parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2]/'.env')
    rows=run_benchmark(args.scenarios,args.output,args.variants,args.repeats,args.seed,args.allow_live)
    print(json.dumps({'attempts':len(rows),'failed_or_escalated':sum(r['status']!='awaiting_approval' for r in rows),
                      'scoring_status':'pending_independent_simulator'},indent=2))
if __name__=='__main__':main()
