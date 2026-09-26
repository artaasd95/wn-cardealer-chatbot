"""Message table definition."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from infrastructure.database.tables.base import Base



class Message(Base):
    """Chat message table."""

    __tablename__ = "message"

    message_id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("session.session_id"), nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    def __repr__(self) -> str:
        """Return a readable representation."""
        return (
            f"Message(message_id={self.message_id}, session_id={self.session_id}, role={self.role})"
        )
