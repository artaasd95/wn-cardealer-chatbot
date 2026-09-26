"""Composition-root rules: one LLM for the process, no per-request construction."""

from __future__ import annotations

import pytest

from config.settings import LLMSettings
from domain.exceptions import ConfigError
from infrastructure.llm.factory import LLMClientFactory
from presentation.api.dependencies import AppDependencies
from tests.fakes import FakeLLM, make_test_settings

pytestmark = pytest.mark.integration


class TestCompositionRoot:
    """Plan: the factory runs once at startup; handlers never build clients."""

    def test_dependencies_are_a_singleton(self, build_app) -> None:
        """Two dependency resolutions return the very same container."""
        build_app(FakeLLM())

        first = AppDependencies.get_instance(AppDependencies._instance.settings)  # type: ignore[union-attr]
        second = AppDependencies.get_instance(AppDependencies._instance.settings)  # type: ignore[union-attr]

        assert first is second

    def test_llm_adapter_is_created_once_at_startup(
        self, database_url: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LLMClientFactory.create runs once; every later resolution reuses it."""
        import presentation.api.dependencies as deps_module

        calls: list[str] = []
        monkeypatch.setattr(
            deps_module.LLMClientFactory,
            "create",
            lambda settings: calls.append(settings.provider) or FakeLLM(),
        )
        settings = make_test_settings(database_url)

        container = AppDependencies.get_instance(settings)
        again = AppDependencies.get_instance(settings)

        assert calls == ["openai_compatible"]
        assert container is again
        assert container.llm is again.llm

    def test_container_exposes_the_port_shapes(self, build_app) -> None:
        """The container offers exactly the abstractions the application needs."""
        build_app(FakeLLM())
        deps = AppDependencies._instance  # type: ignore[union-attr]

        assert isinstance(deps.llm, FakeLLM)
        assert hasattr(deps.car_repo, "search") and hasattr(deps.car_repo, "get_by_id")
        assert hasattr(deps.dealer_repo, "get_by_id")
        assert hasattr(deps.schedule_repo, "save")
        assert hasattr(deps.session_store, "get") and hasattr(deps.session_store, "save")
        # request handlers share one chat service built from those ports
        assert hasattr(deps.chat_service, "chat")

    def test_app_dependencies_reset_rebuilds(self, build_app) -> None:
        """The testing reset really drops the singleton."""
        build_app(FakeLLM())
        first = AppDependencies._instance
        AppDependencies.reset()
        build_app(FakeLLM())
        second = AppDependencies._instance

        assert first is not second
        assert first.llm is not second.llm  # type: ignore[union-attr]


@pytest.mark.parametrize("bad_provider", ["anthropic", "", "openai", "groq"])
def test_unknown_provider_fails_fast(bad_provider: str) -> None:
    """Plan: an unknown LLM_PROVIDER is a startup ConfigError, not a late 500."""

    class _Settings:
        provider = bad_provider
        api_key = "sk-test"
        base_url = "https://x.test/v1"
        model = "m"
        temperature = 0.0
        timeout_seconds = 1
        max_retries = 0

    with pytest.raises(ConfigError, match="Unknown LLM provider"):
        LLMClientFactory.create(_Settings())  # type: ignore[arg-type]


def test_provider_key_matching_is_exact() -> None:
    """A differently-cased provider key never silently matches."""
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        LLMSettings(provider="OpenAI_Compatible", api_key="sk-test")
