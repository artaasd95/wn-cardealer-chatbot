from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

"""Data Transfer Objects for session response boundary."""


class SessionSnapshot(BaseModel):
    """Snapshot of current session state."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "sess_abc123",
                "workflow_state": "CAR_SELECTED",
                "selected_car": "C-001",
                "selected_dealer": "D-001",
                "history_length": 5,
            }
        }
    )

    session_id: str = Field(
        ...,
        description="Session ID.",
    )
    workflow_state: str = Field(
        ...,
        description="Current workflow state.",
    )
    selected_car: str | None = Field(
        None,
        description="Selected car ID, or None.",
    )
    selected_dealer: str | None = Field(
        None,
        description="Selected dealer ID, or None.",
    )
    history_length: int = Field(
        default=0,
        description="Number of messages in conversation history.",
    )
