"""Allowlisted, visible scenario catalog for the dashboard foundation.

No arbitrary uploads, evaluation splits, raw inputs or hidden-truth readers.
Zahra's eventual loader should replace this boundary without changing the views.
"""
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from project.core.schemas import ScenarioInput
from project.core.state import digest

MAX_BYTES = 2_000_000
MAX_FILES = 100
APPROVED_ROOTS = (
    'data/processed/agent_inputs/demo',
    'data/processed/agent_inputs/development',
)
FIXTURE_ROOT = 'tests/core/fixtures'


@dataclass(frozen=True)
class ScenarioChoice:
    key: str
    source: str
    scenario: ScenarioInput
    content_hash: str

    @property
    def label(self):
        return f'{self.scenario.scenario_id} · {len(self.scenario.sites)} sites'


@dataclass(frozen=True)
class ScenarioCatalog:
    choices: tuple[ScenarioChoice, ...]
    issues: tuple[str, ...]
    using_fixtures: bool

    @property
    def default_index(self):
        return next((i for i, item in enumerate(self.choices)
                     if item.scenario.scenario_id == 'DEMO-005'), 0)


def load_catalog(root: Path) -> ScenarioCatalog:
    """Re-read local inputs so file changes invalidate session results by content hash."""
    root = Path(root).resolve()
    issues = []

    def scan(relative_roots, source):
        choices = []
        seen = set()
        inspected = 0
        for relative in relative_roots:
            directory = root / relative
            if not directory.exists():
                continue
            if directory.resolve() != directory:
                issues.append(f'{relative}: skipped a linked input directory.')
                continue
            for path in sorted(directory.glob('*.json')):
                inspected += 1
                if inspected > MAX_FILES:
                    issues.append('Scenario list limited to 100 files; narrow the approved input folders.')
                    return choices
                key = path.relative_to(root).as_posix()
                if not path.resolve().is_relative_to(directory.resolve()):
                    issues.append(f'{key}: skipped a file outside the approved input folder.')
                    continue
                try:
                    if path.stat().st_size > MAX_BYTES:
                        issues.append(f'{key}: exceeds the 2 MB input limit.')
                        continue
                    scenario = ScenarioInput.model_validate_json(path.read_text(encoding='utf-8'))
                except ValidationError as error:
                    # Do not render exception input values: rejected files may contain hidden truth.
                    issues.append(f'{key}: visible-input contract rejected the file ({error.error_count()} errors).')
                    continue
                except (OSError, UnicodeError):
                    issues.append(f'{key}: could not read a UTF-8 input file.')
                    continue
                if scenario.scenario_id in seen:
                    issues.append(f'{key}: duplicate scenario ID; the first valid file is retained.')
                    continue
                seen.add(scenario.scenario_id)
                choices.append(ScenarioChoice(key, source, scenario, digest(scenario)))
        return choices

    choices = scan(APPROVED_ROOTS, 'processed_input')
    using_fixtures = not choices
    if using_fixtures:
        choices = scan((FIXTURE_ROOT,), 'development_fixture')
    return ScenarioCatalog(tuple(choices), tuple(issues), using_fixtures)
