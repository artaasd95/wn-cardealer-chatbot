"""Tests for the Streamlit UI's API URL resolution."""

from __future__ import annotations

import importlib
import sys


def _load_streamlit_app_module():
    """Import the Streamlit app module with fresh module state."""
    module_name = "presentation.streamlit.app"
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def test_default_api_base_url_uses_app_settings(monkeypatch) -> None:
    """The Streamlit UI should follow APP_HOST and APP_PORT by default."""
    monkeypatch.setenv("APP_HOST", "0.0.0.0")
    monkeypatch.setenv("APP_PORT", "8001")
    monkeypatch.delenv("API_BASE_URL", raising=False)

    module = _load_streamlit_app_module()

    assert module.DEFAULT_API_BASE_URL == "http://127.0.0.1:8001"
    assert module.API_BASE_URL == "http://127.0.0.1:8001"


def test_api_base_url_env_override_wins(monkeypatch) -> None:
    """An explicit API_BASE_URL should override the shared app settings."""
    monkeypatch.setenv("APP_HOST", "127.0.0.1")
    monkeypatch.setenv("APP_PORT", "8001")
    monkeypatch.setenv("API_BASE_URL", "http://127.0.0.1:9000")

    module = _load_streamlit_app_module()

    assert module.DEFAULT_API_BASE_URL == "http://127.0.0.1:8001"
    assert module.API_BASE_URL == "http://127.0.0.1:9000"
