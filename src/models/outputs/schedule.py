from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

"""Internal models for schedule records."""


class ScheduleRecord(BaseModel):
    """Persisted schedule record."""

    schedule_id: str = Field(
        ...,
        description="Unique schedule ID.",
    )
    dealer_id: str = Field(
        ...,
        description="Dealer ID.",
    )
    car_id: str = Field(
        ...,
        description="Car ID.",
    )
    scheduled_for: datetime = Field(
        ...,
        description="Scheduled datetime.",
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone.",
    )
    status: str = Field(
        default="confirmed",
        description="Schedule status (e.g., confirmed, pending, cancelled).",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the schedule was created.",
    )
    user_id: str | None = Field(
        None,
        description="Associated user ID.",
    )
