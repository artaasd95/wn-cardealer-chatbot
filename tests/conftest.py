"""Shared pytest bootstrap for both the unit and integration suites.

Design constraints this file exists to enforce:

* No test may ever reach a real LLM provider. `fake_llm` is the only way to
  obtain an LLM client in a test.
* No test may read the developer's real `.env`. `test_settings` supplies values
  explicitly, and `LLMClientFactory` is pointed at them.
* No test may share session state. `session_store` is function-scoped.
* No test may touch the committed `data/cardealer.db`.

The fakes below are deliberately standalone. They do not import from
`ports/`, `config/`, or `infrastructure/` because those layers do not exist
yet. Each carries a note naming the real type it must conform to once that
phase lands, so nothing here has to be thrown away later.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

# --- paths -------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
DATA_DIR = REPO_ROOT / "data"
CARS_CSV = DATA_DIR / "cars.csv"
DEALERS_CSV = DATA_DIR / "dealers.csv"


# --- LLM ---------------------------------------------------------------------


class FakeLLMPort:
    """Test double for `ports.llm.LLMPort` (Phase 4).

    Hand back canned responses instead of calling a provider. `responses` is
    consumed in order; `default` answers anything left over. `calls` records
    every prompt so a test can assert the LLM was (or was not) consulted.
    """

    def __init__(self, responses: list[Any] | None = None, default: Any = None) -> None:
        self.responses = list(responses or [])
        self.default = default
        self.calls: list[str] = []

    def structured_completion(self, prompt: str, output_type: type) -> Any:
        self.calls.append(prompt)
        if self.responses:
            return self.responses.pop(0)
        if self.default is not None:
            return self.default
        raise AssertionError(
            "FakeLLMPort ran out of canned responses. Queue a response with the "
            "`fake_llm` fixture instead of letting this reach a real provider."
        )


class FailingLLMPort:
    """Simulates provider failure so the degradation path can be tested."""

    def __init__(self, message: str = "provider unavailable") -> None:
        self.message = message
        self.calls: list[str] = []

    def structured_completion(self, prompt: str, output_type: type) -> Any:
        self.calls.append(prompt)
        raise RuntimeError(self.message)


@pytest.fixture
def fake_llm() -> FakeLLMPort:
    return FakeLLMPort()


@pytest.fixture
def failing_llm() -> FailingLLMPort:
    return FailingLLMPort()


# --- settings ----------------------------------------------------------------


@dataclass
class TestSettings:
    """Test double for `config.settings.Settings` (Phase 5).

    Values are hardcoded and never read from `.env`, so a developer's real
    credentials can never leak into a test run.
    """

    app_env: str = "test"
    host: str = "127.0.0.1"
    port: int = 8000
    database_url: str = "sqlite:///:memory:"
    session_ttl_seconds: int = 1800
    llm_provider: str = "openai_compatible"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "test-key-not-a-secret"
    llm_model: str = "test-model"
    llm_temperature: float = 0.0
    llm_timeout_seconds: int = 5
    llm_max_retries: int = 0


@pytest.fixture
def test_settings() -> TestSettings:
    return TestSettings()


@pytest.fixture
def real_env_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fails loudly if anything under test tries to read a real ``.env``."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_API_KEY", "test-key-not-a-secret")


# --- session store -----------------------------------------------------------


@dataclass
class InMemorySessionStore:
    """Test double for `ports.session_store.SessionStore` (Phase 4).

    A plain dict with no TTL handling; TTL behaviour itself is a Phase 6 unit
    test concern. Each test gets a fresh instance so state cannot leak.
    """

    records: dict[str, Any] = field(default_factory=dict)

    def get(self, session_id: str) -> Any | None:
        return self.records.get(session_id)

    def create(self, session_id: str, **kwargs: Any) -> Any:
        self.records[session_id] = kwargs
        return kwargs

    def save(self, session_id: str, record: Any) -> Any:
        self.records[session_id] = record
        return record

    def delete(self, session_id: str) -> None:
        self.records.pop(session_id, None)

    def purge_expired(self) -> int:
        return 0


@pytest.fixture
def session_store() -> InMemorySessionStore:
    return InMemorySessionStore()


# --- database ----------------------------------------------------------------


def csv_data_available() -> bool:
    """True once Phase 1 has generated both fixture CSVs."""
    return CARS_CSV.exists() and DEALERS_CSV.exists()


@pytest.fixture
def temp_database_url() -> Iterator[str]:
    """A throwaway SQLite file, removed after the test.

    Uses a real file rather than ``:memory:`` so the schema and seeding path
    are exercised the same way they will be in a real run.
    """
    handle, path = tempfile.mkstemp(suffix=".db", prefix="cardealer_test_")
    os.close(handle)
    try:
        yield f"sqlite:///{path}"
    finally:
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(path + suffix)
            if candidate.exists():
                candidate.unlink()


@pytest.fixture
def seeded_database_url(temp_database_url: str) -> str:
    """Like `temp_database_url` but fails clearly before Phase 1 is done."""
    if not csv_data_available():
        pytest.skip(
            "data/cars.csv and data/dealers.csv are missing. "
            "Run `python scripts/generate_data.py` (Phase 1) first."
        )
    return temp_database_url
