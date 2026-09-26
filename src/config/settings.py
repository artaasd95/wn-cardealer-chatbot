"""Application configuration loaded from .env at startup.

This module reads and validates all environment variables exactly once,
failing fast with clear errors if the configuration is invalid or incomplete.

Configuration is immutable after import; no per-request changes are allowed.
The LLM provider is selected here and never changed during the process lifetime.
"""

from __future__ import annotations

from pydantic import Field, validator
from pydantic_settings import BaseSettings

from domain.exceptions import ConfigError


class LLMSettings(BaseSettings):
    """LLM provider configuration read from .env.

    Supported provider: "openai_compatible"
      This adapter connects to any /v1-compatible endpoint:
      - OpenAI (api.openai.com)
      - Azure OpenAI (your-resource.openai.azure.com)
      - Groq (api.groq.com)
      - Together (api.together.xyz)
      - Ollama (localhost:11434)
      - vLLM (self-hosted)
      - LM Studio (localhost:1234)

    Swapping provider requires only changing LLM_PROVIDER and LLM_BASE_URL
    in .env. No code change needed.
    """

    provider: str = Field(
        default="openai_compatible",
        description="LLM provider key. Currently only 'openai_compatible' is supported.",
    )
    base_url: str = Field(
        default="https://api.openai.com/v1",
        description="Base URL for the LLM endpoint. Change to target Azure, Groq, Ollama, etc.",
    )
    api_key: str = Field(
        default="sk-placeholder",
        description="API key for the LLM provider. Never log or expose this.",
    )
    model: str = Field(
        default="gpt-4o-mini",
        description="Model name or ID available at the endpoint.",
    )
    temperature: float = Field(
        default=0.0,
        description="Temperature for extraction tasks (0.0 = deterministic).",
    )
    timeout_seconds: int = Field(
        default=30,
        description="Request timeout in seconds.",
    )
    max_retries: int = Field(
        default=2,
        description="Max retries on transient failure.",
    )

    @validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Ensure provider is supported.

        Args:
            v: The provider value from .env.

        Returns:
            The validated provider string.

        Raises:
            ValueError: If provider is unknown.
        """
        if v != "openai_compatible":
            raise ValueError(
                f"Unknown LLM_PROVIDER '{v}'. "
                "Only 'openai_compatible' is currently supported. "
                "It works with OpenAI, Azure, Groq, Together, Ollama, vLLM, LM Studio."
            )
        return v

    @validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Ensure api_key is not the placeholder.

        Args:
            v: The api_key value from .env.

        Returns:
            The validated api_key string.

        Raises:
            ValueError: If api_key is the placeholder.
        """
        if v == "sk-placeholder" or v == "your-api-key-here":
            raise ValueError(
                "LLM_API_KEY is not configured. "
                "Edit .env and set LLM_API_KEY to your actual API key."
            )
        return v

    @validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Ensure base_url is a valid URL.

        Args:
            v: The base_url value from .env.

        Returns:
            The validated base_url string.

        Raises:
            ValueError: If base_url is malformed.
        """
        if not v.startswith(("http://", "https://")):
            raise ValueError(
                f"LLM_BASE_URL '{v}' must start with http:// or https://. "
                "Check .env and ensure the URL is complete."
            )
        return v

    class Config:
        """Pydantic settings config."""

        env_prefix = "LLM_"
        case_sensitive = False


class AppSettings(BaseSettings):
    """Application configuration read from .env."""

    env: str = Field(default="development", description="Environment: development or production")
    host: str = Field(default="127.0.0.1", description="API host")
    port: int = Field(default=8000, description="API port")

    class Config:
        """Pydantic settings config."""

        env_prefix = "APP_"
        case_sensitive = False


class DatabaseSettings(BaseSettings):
    """Database configuration read from .env."""

    url: str = Field(
        default="sqlite:///./cardealer.db",
        description="Database connection URL. SQLite default for local development.",
    )
    echo: bool = Field(
        default=False,
        description="Log all SQL statements (noisy; use for debugging only).",
    )

    class Config:
        """Pydantic settings config."""

        env_prefix = "DATABASE_"
        case_sensitive = False


class SessionSettings(BaseSettings):
    """Session configuration read from .env."""

    ttl_seconds: int = Field(
        default=3600,
        description="Session TTL in seconds (1 hour default).",
    )

    class Config:
        """Pydantic settings config."""

        env_prefix = "SESSION_"
        case_sensitive = False


class Settings:
    """Root settings container, read and validated once at startup.

    This is a simple container (not a Pydantic model) to avoid double-validation
    and provide a single point of access to all configuration.

    On instantiation, all subsettings are validated. If any setting is invalid,
    a ConfigError is raised immediately, preventing the app from starting.
    """

    def __init__(self) -> None:
        """Load and validate all settings from .env."""
        try:
            self.llm = LLMSettings()
            self.app = AppSettings()
            self.database = DatabaseSettings()
            self.session = SessionSettings()
        except Exception as e:
            raise ConfigError(
                f"Configuration error at startup. Check .env and your environment. {str(e)}"
            ) from e

    def __repr__(self) -> str:
        """Return a safe repr that never exposes the API key."""
        return (
            f"Settings("
            f"provider={self.llm.provider}, "
            f"base_url={self.llm.base_url}, "
            f"model={self.llm.model}, "
            f"env={self.app.env}"
            f")"
        )
