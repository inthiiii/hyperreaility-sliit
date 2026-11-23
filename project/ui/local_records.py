"""Private atomic decision/simulation records. Checksums are not signatures."""
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from project.core.state import digest
from project.core.tracing import redact


def save_record(directory, record_id, payload):
    name = str(UUID(record_id))
    directory = Path(directory);directory.mkdir(parents=True, exist_ok=True)
    value = redact(payload)
    envelope = {'format_version': 1, 'payload': value, 'sha256': digest(value)}
    path = directory / (name + '.json')
    temporary = directory / ('.' + str(uuid4()) + '.tmp')
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(envelope, stream, indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def read_record(path):
    value = json.loads(Path(path).read_text())
    if value.get('format_version') != 1 or digest(value['payload']) != value['sha256']:
        raise ValueError('Record integrity check failed')
    return value['payload']
