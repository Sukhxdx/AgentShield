"""Fixtures that point the app at a temporary sandbox and audit database."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def settings(tmp_path, monkeypatch):
    """Isolated settings for one test."""
    monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
    monkeypatch.setenv("SANDBOX_DB_PATH", str(tmp_path / "sandbox.db"))
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("DECISION_SECRET", "test-secret")
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path / "results"))
    from backend.config import get_settings

    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def runtime(settings):
    """A fully wired runtime using the temporary databases."""
    from backend.runtime import build_runtime

    return build_runtime(settings)


@pytest.fixture
def client(settings):
    """HTTP client bound to a fresh app."""
    from backend.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def auth_header():
    """API key used by the test client."""
    return {"X-API-Key": "test-key"}
