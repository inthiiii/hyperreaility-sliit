"""Core-only integration runner. Uses no evaluator truth or simulation."""
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv
from project.core.schemas import ScenarioInput
from project.core.coordinator import Coordinator
from project.llm.client import HostedAdapter

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario',required=True)
    parser.add_argument('--mode',choices=['template','single','multi'],default='template')
    parser.add_argument('--planner',choices=['cp_sat','greedy'],default='cp_sat')
    parser.add_argument('--output')
    parser.add_argument('--trace-dir',default='results/local_runs')
    args=parser.parse_args()
    # No broad file-reader tool is given to agents. This CLI accepts a deliberate human-selected input.
    raw=json.loads(Path(args.scenario).read_text())
    scenario=ScenarioInput.model_validate(raw)
    adapter=None
    if args.mode!='template':
        load_dotenv(Path(__file__).resolve().parents[2]/'.env')
        from project.llm.health import preflight
        health=preflight()
        if health['status']=='blocked':
            print(json.dumps(health,indent=2));raise SystemExit(2)
        adapter=HostedAdapter.from_env()
    try:result=Coordinator(adapter,planner=args.planner,trace_dir=args.trace_dir).run(scenario,args.mode)
    finally:
        if adapter:adapter.close()
    value=result.model_dump_json(indent=2)
    if args.output:Path(args.output).write_text(value+'\n')
    print(json.dumps({'status':result.status,'mode':result.mode,'actions':len(result.plan.actions) if result.plan else 0,
                     'reasons':result.reasons,'model_calls':len(result.model_usage),
                     'simulation':'not implemented by this core runner'},indent=2))
    if result.status=='escalated':raise SystemExit(2)
if __name__=='__main__':main()
