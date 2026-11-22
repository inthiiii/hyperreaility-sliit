"""Credential-safe local preflight; no inference or SDK client construction."""
import json
import os
from pathlib import Path
from dotenv import load_dotenv

def preflight(environ=None):
    env=os.environ if environ is None else environ
    provider=env.get('LLM_PROVIDER','openai')
    model=env.get('LLM_MODEL','').strip()
    key_name='OPENROUTER_API_KEY' if provider=='openrouter' else 'OPENAI_API_KEY'
    reasons=[]
    if provider not in ('openai','openrouter'):reasons.append('Unsupported LLM_PROVIDER')
    if not model:reasons.append('Set LLM_MODEL to the exact hosted model ID')
    if not env.get(key_name,'').strip():reasons.append('Missing '+key_name)
    return {'status':'blocked' if reasons else 'configured_unverified','provider':provider,
            'model':model or None,'key_present':bool(env.get(key_name,'').strip()),
            'reasons':reasons,'inference_performed':False}

def main():
    load_dotenv(Path(__file__).resolve().parents[2]/'.env')
    result=preflight();print(json.dumps(result,indent=2))
    return 2 if result['status']=='blocked' else 0
if __name__=='__main__':raise SystemExit(main())
