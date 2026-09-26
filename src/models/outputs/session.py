from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from models.outputs.message import MessageRecord

"""Internal models for session persistence and retrieval."""

# MessageRecord lives in models/outputs/message.py (one contract per file);
# it is re-exported here because session history is typed as list[MessageRecord].
__all__ = ["MessageRecord", "SessionRecord", "SessionSnapshotRecord"]


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
    scheduling_context: dict = Field(
        default_factory=dict,
        description="Scheduling context for call scheduling.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC).replace(tzinfo=None),
        description="When session was created.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC).replace(tzinfo=None),
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
    scheduling_context: dict
    user_id: str | None = None
    expires_at: datetime | None = None
