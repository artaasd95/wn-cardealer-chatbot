"""Message table definition."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.tables.base import Base


class Message(Base):
    """Chat message table."""

    __tablename__ = "message"

    message_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("session.session_id"), index=True)
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        index=True,
    )

    def __repr__(self) -> str:
        """Return a readable representation."""
        return (
            f"Message(message_id={self.message_id}, session_id={self.session_id}, role={self.role})"
        )
