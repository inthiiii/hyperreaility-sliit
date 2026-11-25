"""Unit/integration tests never inherit personal provider credentials or .env files."""
import pytest


@pytest.fixture(autouse=True)
def isolated_provider_environment(monkeypatch):
    monkeypatch.setenv('PYTHON_DOTENV_DISABLED','1')
    for key in ('LLM_PROVIDER','LLM_MODEL','LLM_REASONING_EFFORT','LLM_API','LLM_BASE_URL',
                'OPENAI_API_KEY','OPENROUTER_API_KEY'):
        monkeypatch.delenv(key,raising=False)
