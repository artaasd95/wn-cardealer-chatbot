from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

"""Internal models for schedule records and scheduling-turn outcomes."""


class ScheduleRecord(BaseModel):
    """Persisted schedule record."""

    schedule_id: str = Field(
        ...,
        description="Unique schedule ID.",
    )
    session_id: str = Field(
        ...,
        description="Session the schedule belongs to.",
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
        description="Scheduled datetime (naive UTC).",
    )
    timezone: str = Field(
        default="UTC",
        description="IANA timezone the user asked for.",
    )
    status: str = Field(
        default="confirmed",
        description="Schedule status (e.g., confirmed, pending, cancelled).",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC).replace(tzinfo=None),
        description="When the schedule was created.",
    )
    user_id: str | None = Field(
        None,
        description="Associated user ID.",
    )


class ScheduleOutcome(BaseModel):
    """Result of one scheduling turn.

    ``status`` is one of:
    - ``created``: schedule built, validated and persisted (``record`` is set)
    - ``needs_date`` / ``needs_time`` / ``needs_datetime``: information missing;
      ``question`` asks for exactly that piece
    - ``ambiguous``: input could be read more than one way; ``question`` clarifies
    - ``invalid``: input could not be read; ``question`` asks again
    - ``past``: requested time has already passed; ``question`` asks for a new one
    - ``failed``: persistence failed after a valid schedule was built
    """

    status: str = Field(
        ...,
        description="Outcome classification for this scheduling turn.",
    )
    question: str = Field(
        default="",
        description="Question to ask the user when the schedule was not created.",
    )
    record: ScheduleRecord | None = Field(
        None,
        description="The persisted schedule record, when status is 'created'.",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Fields still needed from the user.",
    )
    reply: str = Field(
        default="",
        description=(
            "Wording for a created schedule (LLM-generated with a deterministic "
            "fallback); empty for the other statuses."
        ),
    )
    context: dict[str, str | None] = Field(
        default_factory=dict,
        description="Partial extraction to carry over into the next turn.",
    )
