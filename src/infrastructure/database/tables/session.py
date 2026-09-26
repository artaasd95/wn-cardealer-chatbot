"""Session table definition."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, String

from infrastructure.database.tables.base import Base


class SessionTable(Base):
    """User session table."""

    __tablename__ = "session"

    session_id = Column(String, primary_key=True)
    user_id = Column(String, nullable=True, index=True)
    workflow_state = Column(String, nullable=False)
    selected_car_id = Column(String, nullable=True)
    selected_dealer_id = Column(String, nullable=True)
    conversation_history = Column(String, nullable=False, default="[]")
    scheduling_context = Column(String, nullable=True, default="{}")
    expires_at = Column(DateTime, nullable=False, index=True)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
    )
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )

    def __repr__(self) -> str:
        """Return a readable representation."""
        return (
            f"Session(session_id={self.session_id}, user_id={self.user_id}, "
            f"state={self.workflow_state})"
        )
