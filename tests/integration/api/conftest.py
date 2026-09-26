"""Fixtures for the API integration suite.

The app under test is built by the real composition root
(``presentation.api.dependencies``) against a throwaway SQLite file seeded
from the Phase 1 CSV fixtures — the only substitution is the LLM port, which
is always a fake so no test can reach a real provider.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from presentation.api.dependencies import AppDependencies
from tests.fakes import FakeLLM, make_test_settings
from ports.llm import LLMPort


@pytest.fixture(autouse=True)
def reset_dependencies() -> Iterator[None]:
    """Keep the AppDependencies singleton from leaking between tests.

    Yields:
        None; the singleton is reset again after the test.
    """
    AppDependencies.reset()
    yield
    AppDependencies.reset()


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    """Throwaway SQLite URL for the app under test.

    Args:
        tmp_path: pytest temp directory.

    Returns:
        SQLAlchemy URL pointing at a fresh file per test.
    """
    return f"sqlite:///{tmp_path}/api-tests.db"


@pytest.fixture
def build_app(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> Callable[[LLMPort], FastAPI]:
    """App factory wired to the real composition root with a fake LLM.

    Args:
        database_url: Throwaway database URL.
        monkeypatch: pytest monkeypatch fixture.

    Returns:
        A callable taking the LLMPort to install and returning a FastAPI app.
    """

    def _build(llm: LLMPort) -> FastAPI:
        import presentation.api.dependencies as deps_module
        from presentation.api.main import create_app

        settings = make_test_settings(database_url)
        monkeypatch.setattr(deps_module.LLMClientFactory, "create", lambda _settings: llm)
        monkeypatch.setattr(deps_module, "get_settings", lambda: settings)
        return create_app(settings)

    return _build


@pytest.fixture
def client(build_app, fake_llm: FakeLLM) -> Iterator[TestClient]:
    """TestClient for the app under test, backed by the scripted fake LLM.

    Args:
        build_app: App factory fixture.
        fake_llm: Scripted LLM port.

    Yields:
        A connected TestClient.
    """
    with TestClient(build_app(fake_llm)) as test_client:
        yield test_client
