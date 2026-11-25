"""Credential-safe local preflight; no inference or SDK client construction."""
import json
import os
from pathlib import Path
from dotenv import load_dotenv

REASONING_EFFORTS = ('none','low','medium','high','xhigh','max')

def preflight(environ=None):
    env=os.environ if environ is None else environ
    provider=env.get('LLM_PROVIDER','openai')
    api_mode=env.get('LLM_API','chat_completions')
    model=env.get('LLM_MODEL','').strip()
    effort=env.get('LLM_REASONING_EFFORT','').strip() or None
    key_name='OPENROUTER_API_KEY' if provider=='openrouter' else 'OPENAI_API_KEY'
    reasons=[]
    if provider not in ('openai','openrouter'):reasons.append('Unsupported LLM_PROVIDER')
    if api_mode not in ('chat_completions','responses') or (api_mode=='responses' and provider!='openai'):reasons.append('Unsupported provider/LLM_API combination')
    if effort is not None and effort not in REASONING_EFFORTS:reasons.append('Unsupported LLM_REASONING_EFFORT')
    if not model:reasons.append('Set LLM_MODEL to the exact hosted model ID')
    if not env.get(key_name,'').strip():reasons.append('Missing '+key_name)
    return {'status':'blocked' if reasons else 'configured_unverified','provider':provider,
            'api_mode':api_mode,'model':model or None,'reasoning_effort':effort,'key_present':bool(env.get(key_name,'').strip()),
            'reasons':reasons,'inference_performed':False}

def main():
    load_dotenv(Path(__file__).resolve().parents[2]/'.env')
    result=preflight();print(json.dumps(result,indent=2))
    return 2 if result['status']=='blocked' else 0
if __name__=='__main__':raise SystemExit(main())
