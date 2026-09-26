"""Session table definition."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.tables.base import Base


class SessionTable(Base):
    """User session table."""

    __tablename__ = "session"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    workflow_state: Mapped[str] = mapped_column(String)
    selected_car_id: Mapped[str | None] = mapped_column(String, nullable=True)
    selected_dealer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    conversation_history: Mapped[str] = mapped_column(String, default="[]")
    scheduling_context: Mapped[str | None] = mapped_column(String, nullable=True, default="{}")
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )

    def __repr__(self) -> str:
        """Return a readable representation."""
        return (
            f"Session(session_id={self.session_id}, user_id={self.user_id}, "
            f"state={self.workflow_state})"
        )
