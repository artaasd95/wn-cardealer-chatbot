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
