from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

"""Data Transfer Objects for chat request boundary."""


class ChatRequest(BaseModel):
    """Incoming chat message from user."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "sess_abc123",
                "message": "I'm looking for a BMW 3-Series",
                "user_id": "user_xyz",
            }
        }
    )

    session_id: str | None = Field(
        None,
        description="Existing session ID, or None to create a new session.",
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User message; must be non-empty and under 2000 characters.",
    )
    user_id: str | None = Field(
        None,
        description="Optional user identifier for tracking.",
    )
