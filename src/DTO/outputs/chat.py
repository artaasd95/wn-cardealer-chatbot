from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

"""Data Transfer Objects for chat response boundary."""


class ChatResponse(BaseModel):
    """Outgoing chat response to the user."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "sess_abc123",
                "reply": "I found a BMW 3-Series from 2023. Would you like details?",
                "workflow_state": "CAR_SELECTED",
                "suggested_actions": ["Get dealer details", "Schedule a call", "Find another car"],
                "requires_input": True,
            }
        }
    )

    session_id: str = Field(
        ...,
        description="Session ID for this conversation.",
    )
    reply: str = Field(
        ...,
        description="The bot's response text.",
    )
    workflow_state: str = Field(
        ...,
        description="Current workflow state (e.g., AWAITING_CAR, CAR_SELECTED).",
    )
    suggested_actions: list[str] = Field(
        default_factory=list,
        description="List of suggested next actions the user can take.",
    )
    requires_input: bool = Field(
        default=True,
        description="Whether the bot is waiting for user input.",
    )


class ClarificationMessage(BaseModel):
    """Response when clarification is needed."""

    reply: str = Field(
        ...,
        description="Question asking for clarification.",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Fields or information still needed.",
    )
    options: list[str] | None = Field(
        None,
        description="Optional list of concrete options to choose from.",
    )
