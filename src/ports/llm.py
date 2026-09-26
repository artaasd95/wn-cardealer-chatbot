"""LLM abstraction layer.

This module defines the LLMPort protocol, which is the only way the application
interacts with any LLM provider. It abstracts away provider-specific details
(OpenAI, Azure, Groq, Ollama, etc.) behind a single schema-constrained interface.

The application never imports an LLM client directly, never constructs one,
and never knows which provider is running. Provider selection and configuration
happen exclusively in infrastructure/llm/factory.py, read from .env.
"""

from __future__ import annotations

from typing import Protocol, TypeVar

T = TypeVar("T")


class LLMPort(Protocol[T]):  # noqa: UP046
    """Protocol for structured LLM completions.

    Implementations of this port are responsible for:
    - Talking to a concrete LLM provider (OpenAI, Azure, Groq, Ollama, etc.)
    - Parsing and constraining output to a given Pydantic schema
    - Handling timeouts and retries with exponential backoff
    - Degrading to a deterministic fallback on unrecoverable failure
    - Never raising an exception into a request handler

    The application layer depends only on this protocol and the factory
    that creates a singleton instance at startup.
    """

    def structured_completion(self, prompt: str, output_type: type[T]) -> T:
        """Execute a structured completion against the LLM.

        Args:
            prompt: The full prompt text sent to the LLM.
            output_type: A Pydantic model class defining the required output schema.
                        The LLM response will be constrained to this schema.

        Returns:
            An instance of output_type populated with the LLM's response,
            or a fallback instance if the provider fails after retries.

        Raises:
            Never. On unrecoverable failure, returns a deterministic fallback
            instance of output_type instead of raising.
        """
        ...
