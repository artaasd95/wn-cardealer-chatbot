"""LLM client factory.

This module is the single dispatch point for creating an LLM adapter at startup.
It reads the LLMSettings provider key and instantiates the matching adapter.

Unknown providers fail fast with a ConfigError before the app serves any request.
The factory is called exactly once, in presentation/api/dependencies.py, and the
resolved client is reused for the process lifetime.
"""

from __future__ import annotations

from config.settings import LLMSettings
from domain.exceptions import ConfigError
from infrastructure.llm.openai_compatible import OpenAICompatibleClient
from ports.llm import LLMPort


class LLMClientFactory:
    """Factory for creating LLM adapter instances.

    Dispatches on provider key from settings. Currently only supports
    "openai_compatible", which works with any /v1-compatible endpoint.
    """

    @staticmethod
    def create(settings: LLMSettings) -> LLMPort:
        """Create an LLM adapter instance.

        Args:
            settings: Validated LLMSettings from .env.

        Returns:
            An LLMPort-implementing client.

        Raises:
            ConfigError: If the provider is unknown or settings are invalid.
        """
        if settings.provider == "openai_compatible":
            return OpenAICompatibleClient(settings)

        raise ConfigError(
            f"Unknown LLM provider '{settings.provider}'. "
            "Only 'openai_compatible' is currently supported. "
            "Check LLM_PROVIDER in .env."
        )
