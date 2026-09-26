"""In-memory session store implementation.

This implementation keeps all sessions in memory with TTL-based expiry.
It's suitable for local development and testing; production deployments
would replace this with a persistent store (Redis, database, etc.).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

from models.outputs.session import SessionRecord, SessionSnapshotRecord
from ports.session_store import SessionStore

logger = logging.getLogger(__name__)


class InMemorySessionStore(SessionStore):
    """In-memory session storage with TTL expiry."""

    def __init__(self) -> None:
        """Initialize the session store."""
        self._sessions: dict[str, SessionRecord] = {}

    def get(self, session_id: str) -> SessionSnapshotRecord | None:
        """Retrieve a session by ID.

        Args:
            session_id: The session identifier.

        Returns:
            SessionSnapshotRecord if found and not expired, None otherwise.
        """
        if session_id not in self._sessions:
            return None

        record = self._sessions[session_id]

        if datetime.utcnow() > record.expires_at:
            del self._sessions[session_id]
            logger.info(f"Session {session_id} expired and removed")
            return None

        return SessionSnapshotRecord(
            session_id=record.session_id,
            workflow_state=record.workflow_state,
            selected_car_id=record.selected_car_id,
            selected_dealer_id=record.selected_dealer_id,
            conversation_history=record.conversation_history,
            scheduling_context=record.scheduling_context,
        )

    def create(self, user_id: str | None = None, ttl_seconds: int = 3600) -> SessionRecord:
        """Create a new session.

        Args:
            user_id: Optional user identifier.
            ttl_seconds: Time-to-live in seconds.

        Returns:
            A new SessionRecord with generated session_id.
        """
        from domain.enums.workflow_state import WorkflowState

        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=ttl_seconds)

        record = SessionRecord(
            session_id=session_id,
            user_id=user_id,
            workflow_state=WorkflowState.START.value,
            selected_car_id=None,
            selected_dealer_id=None,
            conversation_history=[],
            scheduling_context={},
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
        )

        self._sessions[session_id] = record
        logger.info(f"Created session {session_id} (TTL: {ttl_seconds}s)")
        return record

    def save(self, record: SessionRecord) -> None:
        """Persist or update a session.

        Args:
            record: The SessionRecord to save.
        """
        record.updated_at = datetime.utcnow()
        self._sessions[record.session_id] = record
        logger.debug(f"Saved session {record.session_id}")

    def delete(self, session_id: str) -> None:
        """Delete a session by ID.

        Args:
            session_id: The session identifier.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Deleted session {session_id}")

    def purge_expired(self) -> int:
        """Remove all expired sessions.

        Returns:
            The count of sessions deleted.
        """
        now = datetime.utcnow()
        expired = [sid for sid, record in self._sessions.items() if now > record.expires_at]

        for sid in expired:
            del self._sessions[sid]

        if expired:
            logger.info(f"Purged {len(expired)} expired sessions")

        return len(expired)
