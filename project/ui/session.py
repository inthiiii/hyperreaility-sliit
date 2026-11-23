"""Per-user UI state. Never globally cache a CoreSession or operator approval."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from project.core.integration import CoreSession
from project.ui.catalog import ScenarioChoice

SESSION_KEY = 'relink_dashboard'


@dataclass
class DashboardSession:
    session_id: str = field(default_factory=lambda: str(uuid4()))
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    selected_key: str | None = None
    scenario_hash: str | None = None
    selection_revision: int = 0
    core: CoreSession = field(default_factory=CoreSession)
    simulation_result: Any = None
    busy: bool = False
    planning_mode: str = 'template'
    planning_scheduler: str = 'cp_sat'
    planning_generation: int = 0
    planning_requests: set[str] = field(default_factory=set)
    planning_attempt: dict | None = None
    last_decision: Any = None
    decision_history: list = field(default_factory=list)
    review_feedback: dict | None = None
    simulation_requests: set[str] = field(default_factory=set)
    simulation_attempt: dict | None = None
    simulator_label: str | None = None

    def select(self, choice: ScenarioChoice) -> bool:
        if (self.selected_key, self.scenario_hash) == (choice.key, choice.content_hash):
            return False
        self.selected_key = choice.key
        self.scenario_hash = choice.content_hash
        self.selection_revision += 1
        self.core = CoreSession()
        self.simulation_result = None
        self.busy = False
        self.planning_generation = 0
        self.planning_requests.clear()
        self.planning_attempt = None
        self.last_decision = None
        self.review_feedback = None
        self.simulation_requests.clear()
        self.simulation_attempt = None
        self.simulator_label = None
        return True

    def clear_selection(self) -> bool:
        if self.selected_key is None:
            return False
        self.selected_key = self.scenario_hash = None
        self.selection_revision += 1
        self.core = CoreSession()
        self.simulation_result = None
        self.busy = False
        self.planning_generation = 0
        self.planning_requests.clear()
        self.planning_attempt = None
        self.last_decision = None
        self.review_feedback = None
        self.simulation_requests.clear()
        self.simulation_attempt = None
        self.simulator_label = None
        return True


def get_dashboard_session(state) -> DashboardSession:
    if SESSION_KEY not in state:
        state[SESSION_KEY] = DashboardSession()
    return state[SESSION_KEY]
