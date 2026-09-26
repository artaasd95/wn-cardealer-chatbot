"""OpenAI-compatible LLM client adapter.

This module implements LLMPort for any /v1-compatible endpoint:
OpenAI, Azure OpenAI, Groq, Together, Ollama, vLLM, LM Studio, etc.

The adapter handles:
- Structured output via response_format
- Timeout and retry with exponential backoff
- Graceful degradation on failure (fallback response, never exception)
- Error mapping to domain exceptions
"""

from __future__ import annotations

import logging
from typing import TypeVar

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
from pydantic import BaseModel, ValidationError

from config.settings import LLMSettings
from domain.exceptions import ConfigError
from ports.llm import LLMPort

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class OpenAICompatibleClient(LLMPort[T]):
    """LLM adapter for OpenAI-compatible endpoints.

    Works with:
    - OpenAI (api.openai.com)
    - Azure OpenAI
    - Groq
    - Together
    - Ollama (localhost:11434)
    - vLLM (self-hosted)
    - LM Studio (localhost:1234)
    """

    def __init__(self, settings: LLMSettings) -> None:
        """Initialize the client with validated settings.

        Args:
            settings: Validated LLMSettings from config/settings.py.

        Raises:
            ConfigError: If settings are invalid (provider, base_url, api_key).
        """
        self.settings = settings
        try:
            self.client = OpenAI(
                api_key=settings.api_key,
                base_url=settings.base_url,
                timeout=settings.timeout_seconds,
                max_retries=settings.max_retries,
            )
        except Exception as e:
            raise ConfigError(f"Failed to initialize OpenAI client: {str(e)}") from e

    @staticmethod
    def _fallback(output_type: type[T]) -> T:
        """Build a deterministic fallback instance of the requested schema.

        A provider failure must never raise into a request handler, so this
        never lets construction errors escape either: if a required field has
        no default, the instance is built without validation.

        Args:
            output_type: The pydantic model class requested by the caller.

        Returns:
            A default instance of output_type.
        """
        try:
            return output_type()
        except Exception:
            return output_type.model_construct()

    def structured_completion(self, prompt: str, output_type: type[T]) -> T:
        """Execute a structured completion.

        Args:
            prompt: The full prompt text sent to the LLM.
            output_type: A Pydantic model class defining the output schema.

        Returns:
            An instance of output_type populated with the LLM's response,
            or a fallback instance if the provider fails after retries.

        Raises:
            Never. On unrecoverable failure, logs the error and returns
            a fallback instance of output_type (all fields at their default).
        """
        try:
            schema = output_type.model_json_schema()

            response = self.client.beta.chat.completions.parse(
                model=self.settings.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant. "
                            "Always respond with valid JSON matching the provided schema."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": output_type.__name__, "schema": schema, "strict": True},
                },
                temperature=self.settings.temperature,
            )

            try:
                return output_type.model_validate_json(response.choices[0].message.content)
            except ValidationError as e:
                logger.warning(
                    f"LLM response failed validation against schema {output_type.__name__}: {str(e)}. "
                    "Returning fallback."
                )
                return self._fallback(output_type)

        except APITimeoutError:
            logger.warning(
                f"LLM request timed out after {self.settings.timeout_seconds}s. Returning fallback."
            )
            return self._fallback(output_type)

        except APIConnectionError as e:
            logger.warning(f"LLM connection failed: {str(e)}. Returning fallback.")
            return self._fallback(output_type)

        except APIStatusError as e:
            logger.warning(f"LLM provider error ({e.status_code}): {str(e)}. Returning fallback.")
            return self._fallback(output_type)

        except Exception as e:
            logger.error(f"Unexpected error in LLM completion: {str(e)}. Returning fallback.")
            return self._fallback(output_type)
