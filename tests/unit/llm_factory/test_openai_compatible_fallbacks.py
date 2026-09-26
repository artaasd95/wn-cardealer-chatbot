"""OpenAI-compatible adapter failure modes (plan.md §3 "LLM provider/config").

Timeout, connection failure, rate limiting, invalid structured output,
truncated / non-JSON output and empty completions must all degrade to the
deterministic fallback — never an exception into a request handler, and never
an invented answer.
"""

from __future__ import annotations

from typing import Any

import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError

from config.settings import LLMSettings
from domain.exceptions import ConfigError
from infrastructure.llm.factory import LLMClientFactory
from infrastructure.llm.openai_compatible import OpenAICompatibleClient
from models.inputs.response import ResponseWording
from models.inputs.task import TaskDecision

pytestmark = pytest.mark.unit


def _settings() -> LLMSettings:
    """Settings that point at a fake endpoint.

    Returns:
        Validated LLMSettings for the adapter under test.
    """
    return LLMSettings(
        provider="openai_compatible",
        api_key="sk-test-key-not-real",
        base_url="https://llm.test.invalid/v1",
        model="test-model",
        temperature=0.0,
        timeout_seconds=1,
        max_retries=0,
    )


def _client_with(failing_call: Any) -> OpenAICompatibleClient:
    """Build the adapter with a stubbed underlying client.

    Args:
        failing_call: A callable that raises the provider failure under test.

    Returns:
        The adapter wired to the stub.
    """
    client = OpenAICompatibleClient(_settings())
    stub = type("Stub", (), {})()
    stub.beta = type("Beta", (), {})()
    stub.beta.chat = type("Chat", (), {})()
    stub.beta.chat.completions = type("Completions", (), {"parse": staticmethod(failing_call)})()
    client.client = stub
    return client


class TestAdapterFallbacks:
    """Every provider failure returns the schema-default fallback."""

    def test_timeout_returns_fallback(self) -> None:
        """APITimeoutError → fallback instance, no raise."""

        def _boom(**_: Any) -> Any:
            raise APITimeoutError(request=_http_request())

        result = _client_with(_boom).structured_completion("p", ResponseWording)

        assert isinstance(result, ResponseWording)
        assert result.reply == ""

    def test_connection_failure_returns_fallback(self) -> None:
        """APIConnectionError (endpoint down) → fallback, no raise."""

        def _boom(**_: Any) -> Any:
            raise APIConnectionError(request=_http_request())

        result = _client_with(_boom).structured_completion("p", TaskDecision)

        assert result.task_type == "UNKNOWN"

    def test_rate_limit_returns_fallback(self) -> None:
        """HTTP 429 → fallback after the retry budget is exhausted."""

        def _boom(**_: Any) -> Any:
            raise _status_error(429, "rate limited")

        result = _client_with(_boom).structured_completion("p", TaskDecision)

        assert result.task_type == "UNKNOWN"

    def test_unauthorized_wrong_endpoint_credentials_returns_fallback(self) -> None:
        """HTTP 401 (key valid for another endpoint) → fallback."""

        def _boom(**_: Any) -> Any:
            raise _status_error(401, "invalid api key")

        result = _client_with(_boom).structured_completion("p", ResponseWording)

        assert result.reply == ""

    def test_truncated_or_non_json_output_returns_fallback(self) -> None:
        """Unparseable content (streaming cut off, truncated JSON) → fallback."""

        def _partial(**_: Any) -> Any:
            return _response_with('{"reply": "trunc')

        result = _client_with(_partial).structured_completion("p", ResponseWording)

        assert result.reply == ""

    def test_empty_completion_returns_fallback(self) -> None:
        """An empty completion → fallback."""

        def _empty(**_: Any) -> Any:
            return _response_with(None)

        result = _client_with(_empty).structured_completion("p", ResponseWording)

        assert result.reply == ""

    def test_invalid_structured_output_returns_fallback(self) -> None:
        """Valid JSON that violates the schema → fallback."""

        def _wrong_schema(**_: Any) -> Any:
            return _response_with('{"unexpected": 42}')

        result = _client_with(_wrong_schema).structured_completion("p", ResponseWording)

        assert result.reply == ""

    def test_unexpected_error_returns_fallback(self) -> None:
        """Any other provider failure (retry budget, streaming error) → fallback."""

        def _boom(**_: Any) -> Any:
            raise RuntimeError("streaming interrupted mid-response")

        result = _client_with(_boom).structured_completion("p", TaskDecision)

        assert result.task_type == "UNKNOWN"

    def test_prompt_carries_the_request_untouched(self) -> None:
        """The prompt reaches the provider verbatim (no silent truncation)."""
        seen: dict[str, Any] = {}

        def _ok(**kwargs: Any) -> Any:
            seen.update(kwargs)
            return _response_with('{"reply": "hello"}')

        result = _client_with(_ok).structured_completion("the prompt", ResponseWording)

        assert result.reply == "hello"
        assert seen["messages"][1]["content"] == "the prompt"
        assert seen["temperature"] == 0.0


class TestFactoryContract:
    """The factory forwards settings unchanged and fails fast on bad config."""

    def test_settings_are_forwarded_unchanged(self) -> None:
        """The adapter holds the exact settings it was given."""
        settings = _settings()
        llm = LLMClientFactory.create(settings)

        assert isinstance(llm, OpenAICompatibleClient)
        assert llm.settings is settings
        assert llm.settings.model == "test-model"

    def test_factory_rejects_unknown_provider_at_startup(self) -> None:
        """Unknown provider → ConfigError at startup, never at first user turn."""

        class _BadSettings:
            provider = "some-other-vendor"
            api_key = "sk-test"
            base_url = "https://x.test/v1"
            model = "m"
            temperature = 0.0
            timeout_seconds = 1
            max_retries = 0

        with pytest.raises(ConfigError, match="Unknown LLM provider"):
            LLMClientFactory.create(_BadSettings())  # type: ignore[arg-type]

    def test_no_api_key_leaks_into_error_paths(self) -> None:
        """Fallback construction never exposes the key in its output."""
        settings = _settings()

        def _boom(**_: Any) -> Any:
            raise RuntimeError(f"boom for key {settings.api_key}")

        result = _client_with(_boom).structured_completion("p", ResponseWording)

        assert settings.api_key not in result.reply
        assert settings.api_key not in repr(result)


class _FakeMessage:
    def __init__(self, content: str | None) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str | None) -> None:
        self.message = _FakeMessage(content)


def _response_with(content: str | None) -> Any:
    """Build a response shaped like the OpenAI parse() reply.

    Args:
        content: The raw completion text.

    Returns:
        An object with .choices[0].message.content.
    """
    stub = type("Response", (), {})()
    stub.choices = [_FakeChoice(content)]
    return stub


def _status_error(status_code: int, message: str) -> APIStatusError:
    """Build an APIStatusError without needing a real HTTP response.

    Args:
        status_code: The provider's HTTP status.
        message: The provider's error message.

    Returns:
        The constructed APIStatusError.
    """
    import httpx

    response = httpx.Response(status_code, request=_http_request(), text=message)
    return APIStatusError(message=message, response=response, body=None)


def _http_request() -> Any:
    """Build a dummy HTTP request object for provider exceptions.

    Returns:
        An httpx.Request pointed at the fake endpoint.
    """
    import httpx

    return httpx.Request("POST", "https://llm.test.invalid/v1/chat/completions")
