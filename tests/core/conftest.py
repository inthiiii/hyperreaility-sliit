import json
from pathlib import Path
import pytest
from project.core.schemas import ScenarioInput
from project.core.state import build_verified_state
from project.agents.extraction import template_facts

@pytest.fixture
def load_case():
    def load(name='DEMO-005'):
        return ScenarioInput.model_validate_json((Path(__file__).parent/'fixtures'/f'{name}.json').read_text())
    return load

@pytest.fixture
def state(load_case):
    s=load_case()
    return build_verified_state(s,template_facts(s))
