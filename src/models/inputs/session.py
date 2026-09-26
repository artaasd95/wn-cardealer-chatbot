from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

"""Internal models for session context."""


class SchedulingContext(BaseModel):
    """Partial scheduling information collected during a schedule flow."""

    date_raw: str | None = Field(
        default=None,
        description="Raw date input, or None if not yet collected.",
    )
    time_raw: str | None = Field(
        default=None,
        description="Raw time input, or None if not yet collected.",
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone context.",
    )


class SessionContext(BaseModel):
    """Complete session context loaded into memory for a turn."""

    session_id: str = Field(
        ...,
        description="Session ID.",
    )
    workflow_state: str = Field(
        ...,
        description="Current workflow state.",
    )
    conversation_history: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of messages: {role, content, created_at}.",
    )
    selected_car_id: str | None = Field(
        None,
        description="Selected car ID, or None.",
    )
    selected_dealer_id: str | None = Field(
        None,
        description="Selected dealer ID, or None.",
    )
    scheduling_context: SchedulingContext = Field(
        default_factory=lambda: SchedulingContext(),
        description="Partial scheduling info during schedule flow.",
    )
    user_id: str | None = Field(
        None,
        description="Associated user ID.",
    )
