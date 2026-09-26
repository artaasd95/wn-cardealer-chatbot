from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.exceptions import InvalidScheduleError

"""Schedule domain entity."""


@dataclass
class Schedule:
    """Domain entity representing a scheduled call."""

    schedule_id: str
    dealer_id: str
    car_id: str
    scheduled_for: datetime
    timezone: str
    status: str = "confirmed"
    user_id: str | None = None
    created_at: datetime | None = None

    def validate(self) -> None:
        """Validate the schedule; raise InvalidScheduleError if invalid.

        Checks:
        - scheduled_for is not in the past
        - timezone is non-empty
        - status is one of: confirmed, pending, cancelled
        """
        now = datetime.utcnow()
        if self.scheduled_for < now:
            raise InvalidScheduleError(
                f"Scheduled time {self.scheduled_for} is in the past"
            )

        if not self.timezone or not self.timezone.strip():
            raise InvalidScheduleError("Timezone is required and cannot be empty")

        valid_statuses = {"confirmed", "pending", "cancelled"}
        if self.status not in valid_statuses:
            raise InvalidScheduleError(
                f"Status must be one of {valid_statuses}, got {self.status}"
            )

    def is_future(self) -> bool:
        """Check if the scheduled time is in the future.

        Returns:
            True if scheduled_for > now.
        """
        return self.scheduled_for > datetime.utcnow()

    def time_until_scheduled(self) -> int:
        """Return seconds until the scheduled call.

        Returns:
            Total seconds remaining, or negative if in the past.
        """
        delta = self.scheduled_for - datetime.utcnow()
        return int(delta.total_seconds())
