from __future__ import annotations

from pydantic import BaseModel, Field

"""Internal models for schedule extraction."""


class ScheduleExtraction(BaseModel):
    """Raw LLM output: extracted date/time from user input."""

    date_raw: str | None = Field(
        None,
        description="Raw date text as the LLM extracted it, or None.",
    )
    time_raw: str | None = Field(
        None,
        description="Raw time text as the LLM extracted it, or None.",
    )
    timezone: str | None = Field(
        None,
        description="Extracted timezone, or None for UTC.",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence that the extraction is complete and unambiguous.",
    )


class SchedulingContext(BaseModel):
    """Partial scheduling information collected across turns.

    Stored on the session while the user is still answering date/time
    questions, merged into the next turn's extraction.
    """

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
