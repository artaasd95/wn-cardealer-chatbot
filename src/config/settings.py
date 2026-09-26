"""Application configuration loaded from .env at startup.

This module reads and validates all environment variables exactly once,
failing fast with clear errors if the configuration is invalid or incomplete.

Configuration is immutable after import; no per-request changes are allowed.
The LLM provider is selected here and never changed during the process lifetime.
"""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from domain.exceptions import ConfigError


def _model_config(prefix: str) -> SettingsConfigDict:
    """Build shared settings config for one environment prefix."""
    return SettingsConfigDict(
        env_prefix=prefix,
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


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

    model_config = _model_config("LLM_")

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

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Ensure provider is supported."""
        if v != "openai_compatible":
            raise ValueError(
                f"Unknown LLM_PROVIDER '{v}'. Only 'openai_compatible' is currently supported."
            )
        return v

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Ensure api_key is not the placeholder."""
        if v == "sk-placeholder" or v == "your-api-key-here":
            raise ValueError("LLM_API_KEY is not configured. Set it in .env.")
        return v

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Ensure base_url is a valid URL."""
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"LLM_BASE_URL '{v}' must start with http:// or https://.")
        return v


class AppSettings(BaseSettings):
    """Application configuration read from .env."""

    model_config = _model_config("APP_")

    env: str = Field(
        default="development",
        description="Environment: development or production",
    )
    host: str = Field(default="127.0.0.1", description="API host")
    port: int = Field(default=8000, description="API port")
    log_level: str = Field(default="INFO", description="Application log level.")
    log_file: str | None = Field(
        default=None,
        description="Optional rotating log file path.",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log_level is one of the standard library log levels."""
        value = v.strip().upper()
        allowed_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
        if value not in allowed_levels:
            raise ValueError(
                f"APP_LOG_LEVEL '{v}' must be one of {sorted(allowed_levels)}."
            )
        return value

    @field_validator("log_file")
    @classmethod
    def normalize_log_file(cls, v: str | None) -> str | None:
        """Collapse blank file paths to None."""
        if v is None:
            return None
        value = v.strip()
        return value or None


class DatabaseSettings(BaseSettings):
    """Database configuration read from .env."""

    model_config = _model_config("DATABASE_")

    url: str = Field(
        default="sqlite:///./cardealer.db",
        description="Database connection URL.",
    )
    echo: bool = Field(
        default=False,
        description="Log all SQL statements (debugging only).",
    )


class SessionSettings(BaseSettings):
    """Session configuration read from .env."""

    model_config = _model_config("SESSION_")

    ttl_seconds: int = Field(
        default=3600,
        description="Session TTL in seconds (1 hour default).",
    )


class Settings:
    """Root settings container, read and validated once at startup."""

    def __init__(self) -> None:
        """Load and validate all settings from .env."""
        try:
            self.llm_settings = LLMSettings()
            self.app_settings = AppSettings()
            self.database_settings = DatabaseSettings()
            self.session_settings = SessionSettings()
        except Exception as e:
            raise ConfigError("startup", f"Check .env. {str(e)}") from e

    def __repr__(self) -> str:
        """Return a safe repr that never exposes the API key."""
        return (
            f"Settings("
            f"provider={self.llm_settings.provider}, "
            f"model={self.llm_settings.model}, "
            f"env={self.app_settings.env}, "
            f"log_level={self.app_settings.log_level}"
            f")"
        )
