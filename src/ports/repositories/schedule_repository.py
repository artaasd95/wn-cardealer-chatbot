"""Schedule repository abstraction layer.

This module defines the ScheduleRepository protocol, which abstracts how a
completed schedule request is persisted. The application never constructs SQL
and never knows whether schedules land in a database, a queue, or a stub.
"""

from __future__ import annotations

from typing import Protocol

from models.outputs.schedule import ScheduleRecord


class ScheduleRepository(Protocol):
    """Protocol for persisting schedule records."""

    def save(self, record: ScheduleRecord) -> ScheduleRecord:
        """Persist a schedule record.

        Args:
            record: The schedule to store. ``schedule_id`` is already unique.

        Returns:
            The stored record.

        Raises:
            DomainError: If the record cannot be stored (e.g. a referenced
                dealer or car does not exist).
        """
        ...
