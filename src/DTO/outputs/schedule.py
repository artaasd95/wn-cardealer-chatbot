from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

"""Data Transfer Objects for schedule response boundary."""


class ScheduleConfirmation(BaseModel):
    """Confirmation of a scheduled call."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "dealer_id": "D-001",
                "dealer_name": "AutoNation Motors",
                "phone": "+91-22-2204-1001",
                "car_id": "C-001",
                "scheduled_for": "2024-12-26T15:00:00",
                "timezone": "America/New_York",
                "status": "confirmed",
            }
        }
    )

    dealer_id: str = Field(
        ...,
        description="Dealer ID for the call.",
    )
    dealer_name: str = Field(
        ...,
        description=(
            "Dealer name shown in the confirmation. Empty string when the "
            "dealer row is unknown, so the reply degrades to the slot alone."
        ),
    )
    phone: str = Field(
        ...,
        description=(
            "Dealer contact phone number shown in the confirmation. Empty "
            "string when the dealer row carries no phone."
        ),
    )
    car_id: str = Field(
        ...,
        description="Car ID being discussed.",
    )
    scheduled_for: datetime = Field(
        ...,
        description="Scheduled datetime.",
    )
    timezone: str = Field(
        ...,
        description="Timezone of the scheduled time.",
    )
    status: str = Field(
        default="confirmed",
        description="Status of the schedule (e.g., confirmed, pending).",
    )
