from __future__ import annotations

from pydantic import BaseModel, Field

"""Internal model for LLM-generated response wording."""


class ResponseWording(BaseModel):
    """LLM output: the reply text for a completed task.

    Every field has a default so the adapter's deterministic fallback
    (a provider failure must never raise into a request handler) always
    produces a usable instance.
    """

    reply: str = Field(
        default="",
        description="The reply text, or empty when the provider failed.",
    )
