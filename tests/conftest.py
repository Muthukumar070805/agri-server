import pytest
import asyncio

pytest_plugins = []


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def test_env(monkeypatch):
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("PINECONE_API_KEY", "real-pinecone-key-abc123")
    monkeypatch.setenv("MISTRAL_API_KEY", "real-mistral-key-xyz789")
    monkeypatch.setenv("SESSION_REDIS_ENABLED", "false")
    monkeypatch.setenv("LLM_CACHE_ENABLED", "false")
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("REDIS_PORT", "6379")


@pytest.fixture(autouse=True)
def reset_circuits():
    from app.resilience.circuit_breaker import _circuits

    _circuits.clear()
    yield
    _circuits.clear()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from main import app

    return TestClient(app)
