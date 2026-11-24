"""Bounded live development verification with an explicitly selected model.

Never uses held-out evaluation cases and never prints credentials. The model is
selected for this process only; environment files are not edited.
"""
import argparse
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from project.evaluation.runner import run_benchmark
from project.llm.health import preflight

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',required=True,help='Exact OpenAI model ID selected by the operator')
    parser.add_argument('--env-file',type=Path,default=ROOT/'.env')
    parser.add_argument('--output',type=Path,required=True,help='New private results/local_benchmarks directory')
    parser.add_argument('--allow-live',action='store_true',help='Authorize up to two bounded hosted workflow attempts')
    args=parser.parse_args()
    if not args.allow_live:parser.error('Live verification requires --allow-live; no request was made')
    if not args.model.strip():parser.error('Exact model ID must not be blank')
    load_dotenv(args.env_file,override=False)
    os.environ['LLM_PROVIDER']='openai';os.environ['LLM_MODEL']=args.model.strip()
    if preflight()['status']=='blocked':parser.error('OpenAI configuration is incomplete; check the local key without publishing it')
    rows=run_benchmark([ROOT/'data/processed/agent_inputs/demo/DEMO-005.json'],args.output,
                       variants=['single','multi'],repeats=1,allow_live=True)
    print(json.dumps({'output':str(args.output),'attempts':len(rows),'results':[
        {k:r.get(k) for k in ('variant','status','scoring_status','model_calls','input_tokens','output_tokens','returned_models','failure_phase','error_type')}
        for r in rows],'api_cost':None,'claims_multi_agent_superiority':False},indent=2))
    return 0 if all(r['scoring_status']=='scored' for r in rows) else 2


if __name__=='__main__':raise SystemExit(main())
