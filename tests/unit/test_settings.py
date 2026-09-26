"""Tests for config/settings.py."""

from __future__ import annotations

import pytest

from config.settings import LLMSettings, AppSettings, DatabaseSettings, SessionSettings, Settings
from domain.exceptions import ConfigError


class TestLLMSettings:
    """Tests for LLMSettings."""

    def test_valid_settings(self, test_settings: Settings) -> None:
        """Test that valid settings load from .env."""
        llm = test_settings.llm_settings
        assert llm.provider == "openai_compatible"
        assert llm.api_key.startswith("sk-")
        assert llm.model == "gpt-4o-mini"
        assert llm.temperature == 0.0

    def test_invalid_provider(self) -> None:
        """Test that invalid provider raises ValueError."""
        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
            LLMSettings(provider="invalid_provider", api_key="sk-valid")

    def test_placeholder_api_key(self) -> None:
        """Test that placeholder API key is rejected."""
        with pytest.raises(ValueError, match="LLM_API_KEY is not configured"):
            LLMSettings(provider="openai_compatible", api_key="sk-placeholder")

    def test_your_api_key_placeholder(self) -> None:
        """Test that 'your-api-key-here' is rejected."""
        with pytest.raises(ValueError, match="LLM_API_KEY is not configured"):
            LLMSettings(provider="openai_compatible", api_key="your-api-key-here")

    def test_invalid_base_url(self) -> None:
        """Test that invalid base URL is rejected."""
        with pytest.raises(ValueError, match="must start with http"):
            LLMSettings(
                provider="openai_compatible",
                api_key="sk-valid-key-123456",
                base_url="not-a-url",
            )

    def test_base_url_http(self) -> None:
        """Test that http:// URLs are accepted."""
        settings = LLMSettings(
            provider="openai_compatible",
            api_key="sk-valid-key-123456",
            base_url="http://localhost:8000/v1",
        )
        assert settings.base_url == "http://localhost:8000/v1"

    def test_base_url_https(self) -> None:
        """Test that https:// URLs are accepted."""
        settings = LLMSettings(
            provider="openai_compatible",
            api_key="sk-valid-key-123456",
            base_url="https://api.openai.com/v1",
        )
        assert settings.base_url == "https://api.openai.com/v1"


class TestAppSettings:
    """Tests for AppSettings."""

    def test_valid_app_settings(self, test_settings: Settings) -> None:
        """Test that app settings load correctly."""
        app = test_settings.app_settings
        assert app.env in ["development", "production"]
        assert app.host
        assert app.port > 0


class TestDatabaseSettings:
    """Tests for DatabaseSettings."""

    def test_valid_database_settings(self, test_settings: Settings) -> None:
        """Test that database settings load correctly."""
        db = test_settings.database_settings
        assert "sqlite" in db.url or "postgresql" in db.url
        assert isinstance(db.echo, bool)


class TestSessionSettings:
    """Tests for SessionSettings."""

    def test_valid_session_settings(self, test_settings: Settings) -> None:
        """Test that session settings load correctly."""
        session = test_settings.session_settings
        assert session.ttl_seconds > 0


class TestSettingsContainer:
    """Tests for Settings container."""

    def test_settings_loads_all_subsettings(self, test_settings: Settings) -> None:
        """Test that Settings loads all subsettings."""
        assert test_settings.llm_settings is not None
        assert test_settings.app_settings is not None
        assert test_settings.database_settings is not None
        assert test_settings.session_settings is not None

    def test_settings_repr_safe(self, test_settings: Settings) -> None:
        """Test that Settings.__repr__ never exposes API key."""
        repr_str = repr(test_settings)
        assert "sk-" not in repr_str
        assert test_settings.llm_settings.api_key not in repr_str
