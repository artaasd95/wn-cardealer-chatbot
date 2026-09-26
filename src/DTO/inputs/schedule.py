from __future__ import annotations

from pydantic import BaseModel, Field

"""Data Transfer Objects for schedule call request boundary."""


class ScheduleCallRequest(BaseModel):
    """Request to schedule a call with a dealer."""

    dealer_id: str = Field(
        ...,
        description="Dealer ID for the call.",
    )
    car_id: str = Field(
        ...,
        description="Car ID being discussed.",
    )
    date_raw: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Raw date input from user (e.g., 'tomorrow', '2024-12-25').",
    )
    time_raw: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Raw time input from user (e.g., '3pm', '15:00').",
    )
    timezone: str | None = Field(
        "UTC",
        description="Timezone for the scheduled time; defaults to UTC.",
    )
