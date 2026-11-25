"""Evaluator-only access to private simulation truth.

DO NOT import this module from agents, the planner, the coordinator, model
adapters or any agent-facing tool. It reads data/evaluation/ground_truth, which
contains the real world state and scheduled future events. Only the independent
simulator harness and tests use it. tests/data enforces that runtime packages do
not import it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from .loader import CASE_ID, MAX_BYTES, REPO_ROOT, SPLITS, LoaderError

TRUTH_ROOT = REPO_ROOT / 'data' / 'evaluation' / 'ground_truth'


class _Truth(BaseModel):
    model_config = ConfigDict(extra='forbid')


class TruthSite(_Truth):
    equipment_ok: StrictBool
    grid_power_ok: StrictBool


class TruthCrew(_Truth):
    crew_id: str
    location: str
    available_from_min: int = Field(ge=0, strict=True)
    available_until_min: int = Field(gt=0, strict=True)
    skills: list[str]


class TruthGenerator(_Truth):
    generator_id: str
    location: str
    available: StrictBool
    autonomy_minutes: int = Field(gt=0, strict=True)
    deployment_minutes: int = Field(gt=0, strict=True)
    max_deployments: Literal[1] = 1


class TruthPatch(_Truth):
    """Only crew availability changes are supported (the crew-loss fixture)."""
    crew_id: str
    available_until_min: int = Field(ge=0, strict=True)


class OperatorReport(_Truth):
    report_id: str
    source_type: str
    observed_at_min: int = Field(strict=True)
    text: str = Field(min_length=1)


class FutureEvent(_Truth):
    event_id: str
    at_min: int = Field(gt=0, strict=True)
    operator_report: OperatorReport
    truth_patch: TruthPatch


class EvaluatorTruth(_Truth):
    scenario_id: str
    sites: dict[str, TruthSite]
    links: dict[str, StrictBool]
    roads: dict[str, StrictBool]
    crews: list[TruthCrew]
    generators: list[TruthGenerator]
    future_events: list[FutureEvent]
    expected_report_facts: list[dict]
    missing_facts: list
    evaluation_notes: list[str]
    # Evidence v3: reports that carry no operational claim (complaints, notices,
    # injection attempts). Facts citing them are false positives.
    distractor_reports: list[dict] = Field(default_factory=list, exclude_if=lambda value: not value)


class EvaluatorLoader:
    def __init__(self, root: Path | str = TRUTH_ROOT):
        self.root = Path(root).resolve()

    def load(self, scenario_id: str) -> EvaluatorTruth:
        if not CASE_ID.match(scenario_id):
            raise LoaderError('Invalid scenario ID')
        matches = [self.root / s / f'{scenario_id}.json' for s in SPLITS
                   if (self.root / s / f'{scenario_id}.json').is_file()]
        if len(matches) != 1:
            raise LoaderError(f'Truth for {scenario_id} not found uniquely')
        path = matches[0].resolve()
        path.relative_to(self.root)  # symlink escape raises ValueError
        if path.stat().st_size > MAX_BYTES:
            raise LoaderError('Truth file exceeds the size limit')
        truth = EvaluatorTruth.model_validate_json(path.read_bytes())
        if truth.scenario_id != scenario_id:
            raise LoaderError('Truth scenario_id disagrees with file name')
        return truth
