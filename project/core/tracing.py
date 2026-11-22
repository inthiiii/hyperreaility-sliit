"""Private, atomic, redacted run records. Store synthetic/redacted incidents only."""
import json
import os
import re
from pathlib import Path
from uuid import uuid4
from .state import digest

SECRET_FIELDS={'api_key','authorization','openai_api_key','openrouter_api_key','password','token','secret'}
def redact(value):
    if isinstance(value,dict):return {k:('[REDACTED]' if k.lower() in SECRET_FIELDS else redact(v)) for k,v in value.items()}
    if isinstance(value,list):return [redact(v) for v in value]
    if isinstance(value,str):
        value=re.sub(r'\bsk-[A-Za-z0-9_-]+','[REDACTED]',value)
        return re.sub(r'(?i)Bearer\s+[^\s"\']+','Bearer [REDACTED]',value)
    return value

def save_run(result,directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    payload=redact(result.model_dump(mode='json'))
    envelope={'format_version':1,'payload':payload,'sha256':digest(payload)}
    destination=directory/(result.run_id+'.json')
    temporary=directory/('.'+str(uuid4())+'.tmp')
    try:
        descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'w') as stream:
            json.dump(envelope,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination

def read_run(path):
    envelope=json.loads(Path(path).read_text())
    if envelope.get('format_version')!=1 or digest(envelope['payload'])!=envelope['sha256']:
        raise ValueError('Run record integrity check failed')
    return envelope['payload']
