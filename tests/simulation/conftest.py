import pytest

from project.data.evaluator import EvaluatorLoader
from project.data.loader import CaseLoader


@pytest.fixture(scope='session')
def demo():
    return CaseLoader().load_case('demo/DEMO-005.json')


@pytest.fixture
def truth():
    return EvaluatorLoader().load('DEMO-005')
