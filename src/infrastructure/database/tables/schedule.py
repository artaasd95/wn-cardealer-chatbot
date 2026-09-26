"""Schedule table definition."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.tables.base import Base


class Schedule(Base):
    """Scheduled call table."""

    __tablename__ = "schedule"

    schedule_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("session.session_id"), index=True)
    dealer_id: Mapped[str] = mapped_column(String, ForeignKey("dealer.dealer_id"), index=True)
    car_id: Mapped[str] = mapped_column(String, ForeignKey("car.car_id"), index=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime)
    timezone: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )

    def __repr__(self) -> str:
        """Return a readable representation."""
        return (
            f"Schedule(schedule_id={self.schedule_id}, dealer_id={self.dealer_id}, "
            f"scheduled_for={self.scheduled_for}, status={self.status})"
        )
