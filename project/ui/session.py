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

    def select(self, choice: ScenarioChoice) -> bool:
        if (self.selected_key, self.scenario_hash) == (choice.key, choice.content_hash):
            return False
        self.selected_key = choice.key
        self.scenario_hash = choice.content_hash
        self.selection_revision += 1
        self.core = CoreSession()
        self.simulation_result = None
        self.busy = False
        return True

    def clear_selection(self) -> bool:
        if self.selected_key is None:
            return False
        self.selected_key = self.scenario_hash = None
        self.selection_revision += 1
        self.core = CoreSession()
        self.simulation_result = None
        self.busy = False
        return True


def get_dashboard_session(state) -> DashboardSession:
    if SESSION_KEY not in state:
        state[SESSION_KEY] = DashboardSession()
    return state[SESSION_KEY]
