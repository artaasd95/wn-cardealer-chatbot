"""Schedule table definition."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Schedule(Base):
    """Scheduled call table."""

    __tablename__ = "schedule"

    schedule_id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("session.session_id"), nullable=False, index=True)
    dealer_id = Column(String, ForeignKey("dealer.dealer_id"), nullable=False, index=True)
    car_id = Column(String, ForeignKey("car.car_id"), nullable=False, index=True)
    scheduled_for = Column(DateTime, nullable=False)
    timezone = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        """Return a readable representation."""
        return (
            f"Schedule(schedule_id={self.schedule_id}, dealer_id={self.dealer_id}, "
            f"scheduled_for={self.scheduled_for}, status={self.status})"
        )
