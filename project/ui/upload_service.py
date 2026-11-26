"""Add a new incident from a visible-input JSON file.

The file must pass the same ScenarioInput contract as the dataset (unknown keys
such as hidden truth are rejected), must build a verified state, and is stored
locally under .relink/uploads (git-ignored). Uploaded incidents have no simulator
answer, so they can be planned, reviewed and approved but not simulated.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import ValidationError

from project.auth import require
from project.core.schemas import ScenarioInput
from project.core.state import build_verified_state
from project.ui.catalog import MAX_BYTES, UPLOAD_ROOT

CASE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')


class UploadRejected(ValueError):
    pass


def check_upload(data: bytes, existing_ids) -> ScenarioInput:
    if len(data) > MAX_BYTES:
        raise UploadRejected('The file is larger than 2 MB.')
    try:
        json.loads(data)
    except (ValueError, UnicodeError):
        raise UploadRejected('The file is not valid JSON.') from None
    try:
        scenario = ScenarioInput.model_validate_json(data)
    except ValidationError as error:
        problems = [f"{'.'.join(map(str, e['loc'])) or 'document'}: {e['msg']}"
                    for e in error.errors(include_input=False)[:3]]
        raise UploadRejected(f'Not a valid incident ({error.error_count()} problem(s)): ' + '; '.join(problems)) from None
    if not CASE_ID.match(scenario.scenario_id):
        raise UploadRejected('scenario_id may use letters, digits, "-" and "_" only (max 64).')
    if scenario.scenario_id in set(existing_ids):
        raise UploadRejected(f'An incident called {scenario.scenario_id} already exists. Change scenario_id and try again.')
    try:
        build_verified_state(scenario, [])
    except Exception as error:  # noqa: BLE001 - reported to the user
        raise UploadRejected(f'The incident is inconsistent and cannot be planned: {error}'[:300]) from None
    return scenario


def save_upload(root, data: bytes, existing_ids, user):
    require(user, 'upload_scenario')
    scenario = check_upload(data, existing_ids)
    folder = Path(root).resolve() / UPLOAD_ROOT
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{scenario.scenario_id}.json'
    path.write_text(scenario.model_dump_json(indent=2), encoding='utf-8')
    return f'{UPLOAD_ROOT}/{scenario.scenario_id}.json'


def remove_upload(root, key, user):
    require(user, 'upload_scenario')
    if not key.startswith(UPLOAD_ROOT + '/'):
        raise UploadRejected('Only uploaded incidents can be removed.')
    path = Path(root).resolve() / key
    if path.parent != (Path(root).resolve() / UPLOAD_ROOT) or path.suffix != '.json':
        raise UploadRejected('Unknown uploaded incident.')
    path.unlink(missing_ok=True)
