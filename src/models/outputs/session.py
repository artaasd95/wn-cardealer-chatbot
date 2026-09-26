from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

"""Internal models for session persistence and retrieval."""


class MessageRecord(BaseModel):
    """Single message in conversation history."""

    role: str = Field(
        ...,
        description="Role: user or assistant.",
    )
    content: str = Field(
        ...,
        description="Message content.",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the message was created.",
    )


class SessionRecord(BaseModel):
    """Persisted session record shape."""

    session_id: str = Field(
        ...,
        description="Session ID.",
    )
    user_id: str | None = Field(
        None,
        description="Associated user ID.",
    )
    workflow_state: str = Field(
        ...,
        description="Current workflow state.",
    )
    selected_car_id: str | None = Field(
        None,
        description="Selected car ID.",
    )
    selected_dealer_id: str | None = Field(
        None,
        description="Selected dealer ID.",
    )
    conversation_history: list[MessageRecord] = Field(
        default_factory=list,
        description="Message history.",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When session was created.",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When session was last updated.",
    )
    expires_at: datetime | None = Field(
        None,
        description="When session expires.",
    )


class SessionSnapshotRecord(BaseModel):
    """Read shape of session for use cases."""

    session_id: str
    workflow_state: str
    selected_car_id: str | None
    selected_dealer_id: str | None
    conversation_history: list[MessageRecord]
    user_id: str | None
    expires_at: datetime | None
