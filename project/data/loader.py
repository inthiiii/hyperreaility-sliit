"""Allowlisted loader for agent-visible scenario inputs.

This is the only data entry point that runtime agents or the dashboard may use.
It can read exactly one kind of file: a processed agent input JSON file stored as
``<root>/<split>/<CASE-ID>.json`` where ``<split>`` is a known split name. It is
not a general filesystem reader. Evaluator truth and raw synthetic files are
served by ``project.data.evaluator``, which agents must never import.
"""
from __future__ import annotations

import re
from pathlib import Path

from project.core.schemas import ScenarioInput

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_INPUT_ROOT = REPO_ROOT / 'data' / 'processed' / 'agent_inputs'
SPLITS = ('demo', 'development', 'candidate_evaluation')
CASE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')
MAX_BYTES = 2_000_000


class LoaderError(ValueError):
    """The requested path is outside the allowlist or the file is invalid."""


class CaseLoader:
    def __init__(self, root: Path | str = AGENT_INPUT_ROOT):
        self.root = Path(root).resolve()

    def _allowed(self, path: str | Path) -> Path:
        raw = Path(path)
        # Relative inputs are interpreted below the allowlisted root only.
        if not raw.is_absolute():
            if '..' in raw.parts:
                raise LoaderError('Path traversal is not permitted')
            raw = self.root / raw
        elif '..' in raw.parts:
            raise LoaderError('Path traversal is not permitted')
        try:
            resolved = raw.resolve(strict=True)
        except (FileNotFoundError, OSError) as exc:
            raise LoaderError(f'Unknown case file: {path}') from exc
        try:
            relative = resolved.relative_to(self.root)
        except ValueError as exc:
            raise LoaderError('Path is outside the approved agent input directory') from exc
        if len(relative.parts) != 2 or relative.parts[0] not in SPLITS:
            raise LoaderError('Only <split>/<case>.json files are permitted')
        if resolved.suffix != '.json' or not CASE_ID.match(resolved.stem) or not resolved.is_file():
            raise LoaderError('Only processed case JSON files are permitted')
        if resolved.stat().st_size > MAX_BYTES:
            raise LoaderError('Case file exceeds the size limit')
        return resolved

    def load_case(self, path: str | Path) -> ScenarioInput:
        """Validate a processed case against the shared version 0.1 schema."""
        resolved = self._allowed(path)
        return ScenarioInput.model_validate_json(resolved.read_bytes())

    def find(self, scenario_id: str) -> Path:
        """Resolve a scenario ID such as DEMO-005 to its approved file."""
        if not CASE_ID.match(scenario_id):
            raise LoaderError('Invalid scenario ID')
        matches = [self.root / s / f'{scenario_id}.json' for s in SPLITS
                   if (self.root / s / f'{scenario_id}.json').is_file()]
        if len(matches) != 1:
            raise LoaderError(f'Scenario {scenario_id} not found uniquely')
        return matches[0]

    def case_ids(self) -> list[str]:
        return sorted(p.stem for s in SPLITS if (self.root / s).is_dir()
                      for p in (self.root / s).glob('*.json'))


_DEFAULT = CaseLoader()


def load_case(path: str | Path) -> ScenarioInput:
    """Shared function agreement: load_case(path) -> ScenarioInput."""
    return _DEFAULT.load_case(path)
