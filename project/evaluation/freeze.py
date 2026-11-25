"""Configuration freeze for the held-out (EVAL2) benchmark.

``create`` records, before any evaluation run:
  * SHA-256 of every EVAL2 input and truth file in the dataset,
  * the agent protocol, task prompts and output caps (hash of the registry),
  * the hosted model configuration (provider, model, API mode, reasoning; never keys),
  * whole-run budgets, the git commit and whether the tree was clean.

``verify`` recomputes all of it at run time. Any drift stops the benchmark, so
prompts cannot be tuned on held-out results without it being visible.

    python -m project.evaluation.freeze create --data-root releases/evidence-v3-20261126/data \
        --output releases/evidence-v3-20261126/FREEZE.json
    python -m project.evaluation.freeze verify --freeze releases/evidence-v3-20261126/FREEZE.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from project.agents import registry as R
from project.core.state import digest

ROOT = Path(__file__).resolve().parents[2]
SPLIT = 'candidate_evaluation'


class FreezeError(ValueError):
    pass


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dataset_hashes(data_root):
    data_root = Path(data_root)
    out = {}
    for kind in ('processed/agent_inputs', 'evaluation/ground_truth'):
        for path in sorted((data_root / kind / SPLIT).glob('*.json')):
            out[f'{kind}/{SPLIT}/{path.name}'] = _sha(path)
    if not out:
        raise FreezeError(f'No {SPLIT} files under {data_root}')
    return out


def protocol_fingerprint():
    agents = [R.INVESTIGATOR, *R.SPECIALISTS, R.REVIEWER]
    return {'protocol': R.PROTOCOL_VERSION,
            'agents': {a.role: {'stage': a.stage, 'task_sha256': hashlib.sha256(a.task.encode()).hexdigest(),
                                'max_output': a.max_output, 'schema_sha256': digest(a.output.model_json_schema())}
                       for a in agents},
            'single_task_sha256': hashlib.sha256(R.SINGLE_ANALYSE_TASK.encode()).hexdigest(),
            'single_max_output': R.SINGLE_ANALYSE_MAX_OUTPUT,
            'rules_sha256': digest(R.RULES)}


def model_settings():
    return {'provider': os.environ.get('LLM_PROVIDER', 'openai'), 'model': os.environ.get('LLM_MODEL', ''),
            'api_mode': os.environ.get('LLM_API', 'chat_completions'),
            'reasoning_effort': os.environ.get('LLM_REASONING_EFFORT', '') or None,
            'base_url_sha256': hashlib.sha256(os.environ.get('LLM_BASE_URL', '').encode()).hexdigest()}


def _git(*args):
    try:
        return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def build(data_root, limits):
    return {'format': 1, 'dataset': str(Path(data_root).resolve().relative_to(ROOT)) if Path(data_root).resolve().is_relative_to(ROOT) else str(data_root),
            'files': dataset_hashes(data_root), 'protocol': protocol_fingerprint(), 'model': model_settings(),
            'limits': dict(limits)}


def create(data_root, output, limits, *, allow_dirty=False):
    commit, dirty = _git('rev-parse', 'HEAD'), bool(_git('status', '--porcelain', '--', 'project', 'releases'))
    if dirty and not allow_dirty:
        raise FreezeError('Commit code and data before freezing (project/ or releases/ has uncommitted changes)')
    if not model_settings()['model']:
        raise FreezeError('LLM_MODEL is not configured')
    record = {**build(data_root, limits), 'git_commit': commit, 'tree_clean': not dirty,
              'created_at_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'Script-generated synthetic EVAL2 cases (evidence v3); not independently human-reviewed. '
                       'Frozen so held-out results cannot feed back into prompts or settings.'}
    output = Path(output)
    if output.exists():
        raise FreezeError(f'{output} already exists; a freeze is create-only')
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    return record


def verify(freeze_path, data_root=None, limits=None):
    record = json.loads(Path(freeze_path).read_text())
    data_root = Path(data_root) if data_root else ROOT / record['dataset']
    current = build(data_root, limits if limits is not None else record['limits'])
    problems = []
    for key in ('files', 'protocol', 'model', 'limits'):
        if current[key] != record[key]:
            problems.append(f'{key} changed since the freeze')
    if problems:
        raise FreezeError('; '.join(problems))
    return {'freeze_sha256': _sha(freeze_path), 'git_commit_at_freeze': record.get('git_commit'),
            'created_at_utc': record.get('created_at_utc'), 'scope': record.get('scope'),
            'eval_files': len(record['files'])}


def main(argv=None):
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=False)
    from project.evaluation.runner import LIMITS
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)
    c = sub.add_parser('create')
    c.add_argument('--data-root', required=True, type=Path)
    c.add_argument('--output', required=True, type=Path)
    v = sub.add_parser('verify')
    v.add_argument('--freeze', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = create(args.data_root, args.output, LIMITS) if args.command == 'create' else verify(args.freeze)
    except FreezeError as error:
        print(f'Freeze error: {error}', file=sys.stderr)
        return 1
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
