"""Bounded, read-only local history. No run/approval restoration or model calls."""
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import islice
import csv
import io
import json
import math
from pathlib import Path
from uuid import UUID

from project.core.coordinator import RunResult
from project.core.schemas import SimulationResult
from project.core.state import digest
from project.core.tracing import redact
from project.ui.review_service import DecisionRecord
from project.ui.confirmation_service import ConfirmationRecord

MAX_BYTES = 8_000_000
MAX_RECORDS = 200
MAX_TOTAL_BYTES = 32_000_000
MAX_SCAN_PER_KIND = 1000
KINDS = {'run': '', 'decision': 'decisions', 'simulation': 'simulation_attempts', 'attempt': 'ui_attempts', 'confirmation': 'confirmations'}
HIDDEN_KEYS = {'ground_truth', 'isolated_truth', 'evaluation_truth', 'raw_truth', 'future_events', 'hidden_events'}


def public_payload(value):
    def strip(item):
        if isinstance(item, dict):
            return {key: strip(child) for key, child in item.items()
                    if key.casefold() not in HIDDEN_KEYS and not key.casefold().startswith('hidden_')}
        if isinstance(item, list):
            return [strip(child) for child in item]
        return item
    return redact(strip(value))


@dataclass(frozen=True)
class HistoryEntry:
    kind: str
    record_id: str
    run_id: str | None
    scenario_id: str
    status: str
    timestamp: str
    relative_path: str
    integrity: str
    payload: dict

    @property
    def key(self):
        return self.kind + ':' + self.record_id


@dataclass(frozen=True)
class HistoryCatalog:
    entries: tuple[HistoryEntry, ...]
    issues: tuple[str, ...]


def _validate(kind, payload, filename):
    if kind == 'run':
        result = RunResult.model_validate(payload)
        if result.mode not in ('template', 'single', 'multi'):
            raise ValueError('Unknown run mode')
        if result.run_id != filename or result.state.source_hash != digest(result.state.scenario):
            raise ValueError('Run identity/input hash mismatch')
        if result.state.scenario_id != result.state.scenario.scenario_id:
            raise ValueError('Run scenario mismatch')
        if result.plan and (result.plan.scenario_id, result.plan.state_version, result.plan.state_hash) != (
                result.state.scenario_id, result.state.state_version, digest(result.state)):
            raise ValueError('Run plan/state mismatch')
        return result.run_id, result.state.scenario_id, result.status, result.metadata.get('started_at_utc')
    if kind == 'decision':
        record = DecisionRecord.model_validate(payload)
        if record.decision_id != filename:
            raise ValueError('Decision identity mismatch')
        return record.run_id, record.scenario_id, record.approval.decision, record.recorded_at_utc.isoformat()
    if kind == 'confirmation':
        record = ConfirmationRecord.model_validate(payload)
        if record.confirmation_id != filename or record.updated_state.scenario_id != record.scenario_id:
            raise ValueError('Confirmation identity mismatch')
        if (record.updated_state.source_hash != record.input_hash_after or
                digest(record.updated_state.scenario) != record.input_hash_after or
                record.report.source_type != 'operator_confirmation' or
                not any(r == record.report for r in record.updated_state.scenario.reports)):
            raise ValueError('Confirmation input/evidence binding mismatch')
        return record.run_id, record.scenario_id, 'recorded', record.recorded_at_utc.isoformat()
    if payload.get('attempt_id') != filename or not isinstance(payload.get('scenario_id'), str):
        raise ValueError('Attempt identity mismatch')
    if kind == 'simulation':
        statuses = ('starting', 'completed', 'failed', 'unsupported')
        if payload.get('status') == 'completed':
            result = SimulationResult.model_validate(payload.get('result'))
            if payload.get('result_hash') != digest(result) or (result.scenario_id, result.state_version) != (
                    payload['scenario_id'], payload.get('state_version')):
                raise ValueError('Simulation output identity/hash mismatch')
    else:
        statuses = ('starting', 'failed', 'blocked', 'awaiting_approval', 'escalated')
        allowed = {'format_version', 'attempt_id', 'request_key', 'started_at_utc', 'finished_at_utc',
                   'scenario_id', 'input_hash', 'mode', 'planner', 'status', 'model_usage', 'warnings',
                   'run_id', 'configured_provider', 'configured_model', 'error_code', 'error_type', 'reasons'}
        if not set(payload) <= allowed:
            raise ValueError('Unknown UI attempt fields')
    if kind == 'attempt' and (not isinstance(payload.get('model_usage', []), list) or any(not isinstance(item, dict) for item in payload.get('model_usage', []))):
        raise ValueError('Malformed usage records')
    if payload.get('status') not in statuses:
        raise ValueError('Unknown attempt status')
    return payload.get('run_id'), payload['scenario_id'], payload['status'], payload.get('started_at_utc')


def load_history(root):
    root = Path(root).resolve()
    base = root / 'results/local_runs'
    issues = [];candidates = [];entries = []
    if not base.exists():
        return HistoryCatalog((), ())
    if base.resolve() != base:
        return HistoryCatalog((), ('Linked local-run directory was skipped.',))
    for kind, relative in KINDS.items():
        directory = base / relative
        if not directory.exists():
            continue
        if directory.resolve() != directory:
            issues.append(f'{kind}: linked history directory skipped.');continue
        try:
            paths = list(islice(directory.glob('*.json'), MAX_SCAN_PER_KIND + 1))
            if len(paths) > MAX_SCAN_PER_KIND:
                issues.append(f'{kind}: scan limited to {MAX_SCAN_PER_KIND} filenames.')
            for path in paths[:MAX_SCAN_PER_KIND]:
                if path.resolve() != path:
                    issues.append(f'{kind}: linked record skipped.');continue
                try:
                    UUID(path.stem)
                    stat = path.stat()
                    candidates.append((stat.st_mtime, kind, path, stat.st_size))
                except (ValueError, OSError):
                    issues.append(f'{kind}: invalid filename or unreadable record skipped.')
        except OSError:
            issues.append(f'{kind}: history directory could not be listed.')
    candidates.sort(key=lambda item: (item[0], item[2].name), reverse=True)
    if len(candidates) > MAX_RECORDS:
        issues.append(f'History limited to the {MAX_RECORDS} most recently modified candidate files.')
    consumed = 0
    for modified, kind, path, size in candidates[:MAX_RECORDS]:
        try:
            if size > MAX_BYTES:
                raise ValueError('Record exceeds size limit')
            if consumed + size > MAX_TOTAL_BYTES:
                issues.append('History byte window exhausted; remaining records were not loaded.');break
            with path.open('rb') as stream:
                raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError('Record exceeds size limit')
            consumed += len(raw)
            envelope = json.loads(raw)
            if kind == 'attempt':
                payload = envelope
            else:
                if envelope.get('format_version') != 1 or digest(envelope['payload']) != envelope['sha256']:
                    raise ValueError('Record integrity check failed')
                payload = envelope['payload']
            def finite_tree(value):
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError('Non-finite record value')
                if isinstance(value, dict):
                    for item in value.values():finite_tree(item)
                if isinstance(value, list):
                    for item in value:finite_tree(item)
            finite_tree(payload)
            run_id, scenario, status, timestamp = _validate(kind, payload, path.stem)
            stamp = datetime.fromisoformat(timestamp) if timestamp else datetime.fromtimestamp(modified, timezone.utc)
            if stamp.tzinfo is None:
                raise ValueError('Recorded timestamp must declare its timezone')
            entries.append(HistoryEntry(kind, path.stem, run_id, scenario, status,
                stamp.astimezone(timezone.utc).isoformat(), path.relative_to(root).as_posix(),
                'Unchecksummed metadata' if kind == 'attempt' else 'Checksum checked; not signed', payload))
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RecursionError, OverflowError):
            # Avoid echoing malformed values, file contents or raw exceptions.
            issues.append(f'{kind}/{path.name}: invalid, inconsistent, oversized or unreadable record skipped.')
    entries.sort(key=lambda entry: entry.timestamp, reverse=True)
    return HistoryCatalog(tuple(entries), tuple(issues))


def filter_history(catalog, kind='All', scenario='All', query=''):
    query = query.strip().casefold()
    return [entry for entry in catalog.entries if (kind == 'All' or entry.kind == kind)
            and (scenario == 'All' or entry.scenario_id == scenario)
            and (not query or query in ' '.join((entry.kind, entry.record_id, entry.run_id or '', entry.scenario_id, entry.status)).casefold())]


def summary_rows(entries):
    rows = []
    for entry in entries:
        payload = public_payload(entry.payload)
        usage = payload.get('model_usage', [])
        metadata = payload.get('metadata', {})
        row = {'Type': entry.kind, 'Record': entry.record_id, 'Run': entry.run_id or '',
               'Scenario': entry.scenario_id, 'Status': entry.status, 'UTC': entry.timestamp,
               'Integrity': entry.integrity, 'Mode': payload.get('mode', ''),
               'Operator': payload.get('approval', {}).get('operator_id', payload.get('operator_id', ''))}
        if entry.kind in ('run', 'attempt'):
            row['Model calls'] = len(usage)
            def reported(field):
                if not usage:return 0
                values = [item.get(field) for item in usage]
                return sum(values) if all(type(value) in (int, float) and math.isfinite(value) and value >= 0 for value in values) else None
            row['Reported input tokens'] = reported('input_tokens')
            row['Reported output tokens'] = reported('output_tokens')
            row['Duration (s)'] = metadata.get('duration_seconds')
        rows.append(row)
    return rows


def json_export(value):
    return json.dumps(public_payload(value), indent=2, ensure_ascii=False, allow_nan=False)


def csv_export(rows):
    rows = public_payload(rows)
    columns = list(dict.fromkeys(key for row in rows for key in row))
    def cell(value):
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        if isinstance(value, str) and (value.startswith(('\t', '\r', '\n')) or value.lstrip().startswith(('=', '+', '-', '@'))):
            return "'" + value
        return value
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow([cell(column) for column in columns])
    for row in rows:
        writer.writerow([cell(row.get(column)) for column in columns])
    return stream.getvalue()


def linked_simulation(entry, catalog):
    """Only correlate historical output; never make a record an active approval."""
    if entry.kind != 'simulation' or entry.status != 'completed':
        return None, 'No completed output in this record.'
    payload = entry.payload
    run_entry = next((item for item in catalog.entries if item.kind == 'run' and item.run_id == entry.run_id), None)
    if run_entry is None:
        return None, 'Matching run is outside this history window or unavailable; outcome is not plotted.'
    result = RunResult.model_validate(run_entry.payload)
    if result.plan is None:
        return None, 'Matching run has no plan; outcome is not plotted.'
    binding = digest({'run': result.run_id, 'input': result.state.source_hash,
                      'plan': digest(result.plan), 'state': digest(result.state)})
    simulation = SimulationResult.model_validate(payload['result'])
    if payload.get('binding') != binding or payload.get('plan_hash') != digest(result.plan) or (simulation.scenario_id, simulation.plan_id, simulation.state_version) != (result.state.scenario_id, result.plan.plan_id, result.state.state_version):
        return None, 'Output/run binding does not match; outcome is not plotted.'
    if len(set(simulation.completed_actions)) != len(simulation.completed_actions) or not set(simulation.completed_actions) <= {action.action_id for action in result.plan.actions}:
        return None, 'Completed action references are invalid; outcome is not plotted.'
    matched = any(item.kind == 'decision' and item.run_id == result.run_id
                  and item.payload.get('binding') == binding
                  and item.payload.get('approval', {}).get('decision') == 'approve'
                  and item.payload['approval'].get('plan_hash') == digest(result.plan)
                  and item.payload['approval'].get('state_hash') == digest(result.state)
                  and item.payload['approval'].get('operator_id') == payload.get('operator_id')
                  and item.payload['approval'].get('plan_id') == result.plan.plan_id
                  and item.payload['approval'].get('state_version') == result.state.state_version
                  and item.payload.get('input_hash') == result.state.source_hash
                  and item.payload.get('scenario_id') == result.state.scenario_id
                  for item in catalog.entries)
    if not matched:
        return None, 'Matching approval audit is outside this history window or unavailable; outcome is not plotted.'
    return simulation, None
