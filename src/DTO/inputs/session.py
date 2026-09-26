from __future__ import annotations

from pydantic import BaseModel, Field

"""Data Transfer Objects for session request boundary."""


class SessionRequest(BaseModel):
    """Request to load or reference a session."""

    session_id: str = Field(
        ...,
        description="Session ID to load.",
    )
    user_id: str | None = Field(
        None,
        description="Optional user ID for validation.",
    )


class CreateSessionRequest(BaseModel):
    """Request to create a new session."""

    user_id: str | None = Field(
        None,
        description="Optional user ID to associate with the new session.",
    )
