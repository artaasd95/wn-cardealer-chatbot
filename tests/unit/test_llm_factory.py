"""Tests for infrastructure/llm/factory.py."""

from __future__ import annotations

import pytest

from config.settings import LLMSettings
from infrastructure.llm.factory import LLMClientFactory
from ports.llm import LLMPort


class TestLLMClientFactory:
    """Tests for LLMClientFactory."""

    def test_create_openai_compatible(self, test_settings) -> None:
        """Test creating an openai_compatible client."""
        llm = LLMClientFactory.create(test_settings.llm_settings)
        assert llm is not None
        assert isinstance(llm, LLMPort)

    def test_create_with_openai_compatible_settings(self) -> None:
        """Test creating with explicit openai_compatible settings."""
        settings = LLMSettings(
            provider="openai_compatible",
            api_key="sk-test-key-123456",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            temperature=0.0,
            timeout_seconds=30,
            max_retries=2,
        )
        llm = LLMClientFactory.create(settings)
        assert llm is not None

    def test_unknown_provider_raises_config_error(self) -> None:
        """Test that unknown provider raises ValueError."""
        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
            LLMSettings(
                provider="unknown_provider",
                api_key="sk-test-key-123456",
            )
