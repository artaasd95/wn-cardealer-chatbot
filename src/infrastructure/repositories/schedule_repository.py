"""Schedule repository implementation.

Persists ScheduleRecord rows into the ``schedule`` table. Foreign keys to
``dealer`` and ``car`` are declared on the table, so a record referencing a
dealer or car that does not exist fails here rather than silently.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from domain.exceptions import DomainError
from infrastructure.database.tables.schedule import Schedule as ScheduleRow
from models.outputs.schedule import ScheduleRecord
from ports.repositories.schedule_repository import ScheduleRepository

logger = logging.getLogger(__name__)


class ScheduleRepositoryImpl(ScheduleRepository):
    """SQLAlchemy-based schedule repository."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        """Initialize with a session factory.

        Args:
            session_factory: A callable (typically ``database.SessionLocal``)
                that produces a SQLAlchemy Session per operation.
        """
        self._session_factory = session_factory

    def save(self, record: ScheduleRecord) -> ScheduleRecord:
        """Persist a schedule record.

        Args:
            record: The schedule to store.

        Returns:
            The stored record.

        Raises:
            DomainError: If the row cannot be inserted.
        """
        row = ScheduleRow(
            schedule_id=record.schedule_id,
            session_id=record.session_id,
            dealer_id=record.dealer_id,
            car_id=record.car_id,
            scheduled_for=record.scheduled_for,
            timezone=record.timezone,
            status=record.status,
            created_at=record.created_at,
        )

        try:
            with self._session_factory() as session:
                session.add(row)
                session.commit()
        except Exception as exc:
            logger.error("failed to persist schedule %s: %s", record.schedule_id, exc)
            raise DomainError(f"Could not store the schedule: {exc}") from exc

        logger.info(
            "schedule %s stored for dealer %s at %s",
            record.schedule_id,
            record.dealer_id,
            record.scheduled_for,
        )
        return record
