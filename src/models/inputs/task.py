from __future__ import annotations

from pydantic import BaseModel, Field

"""Internal models for task decision."""


class TaskDecision(BaseModel):
    """LLM's task intent decision."""

    task_type: str = Field(
        default="UNKNOWN",
        description=(
            "Identified task type: ITEM_LOOKUP, DEALER_DETAILS, SCHEDULE_CALL, "
            "or UNKNOWN. Defaults to UNKNOWN so a provider failure degrades to "
            "a clarification instead of an error."
        ),
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence in the classification (0–1).",
    )
    reason: str | None = Field(
        None,
        description="Optional reasoning for the classification.",
    )
