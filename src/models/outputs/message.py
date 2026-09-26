from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

"""Internal model for a single persisted conversation message."""


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
        default_factory=lambda: datetime.now(UTC).replace(tzinfo=None),
        description="When the message was created.",
    )
