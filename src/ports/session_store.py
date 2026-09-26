"""Session storage abstraction layer.

This module defines the SessionStore protocol, which manages the lifecycle
of user sessions: creation, retrieval, updates, expiry, and cleanup.

The session is the authoritative holder of:
- Conversation history
- Workflow state
- Selected car and dealer
- Scheduling context
- TTL expiry

The application never touches the session store directly; it always goes
through application/session/service.py, which coordinates state transitions.
"""

from __future__ import annotations

from typing import Protocol

from models.outputs.session import SessionRecord, SessionSnapshotRecord


class SessionStore(Protocol):
    """Protocol for session persistence and retrieval.

    Implementations of this port are responsible for:
    - Creating new sessions with TTL-based expiry
    - Retrieving sessions by session_id, returning None if expired
    - Persisting updated sessions atomically
    - Deleting sessions on user request
    - Purging expired sessions periodically (optional)

    Session state is the single authoritative holder of workflow state.
    Once a workflow transition is committed to the session store, it is
    durable for that session lifetime.
    """

    def get(self, session_id: str) -> SessionSnapshotRecord | None:
        """Retrieve a session by ID.

        Args:
            session_id: The session identifier.

        Returns:
            A SessionSnapshotRecord if the session exists and is not expired.
            None if the session does not exist or has expired.
        """
        ...

    def create(self, user_id: str | None = None, ttl_seconds: int = 3600) -> SessionRecord:
        """Create a new session.

        Args:
            user_id: Optional user identifier to associate with this session.
            ttl_seconds: Time-to-live in seconds. Defaults to 3600 (1 hour).

        Returns:
            A new SessionRecord with a generated session_id, ready to persist.
        """
        ...

    def save(self, record: SessionRecord) -> None:
        """Persist or update a session.

        Args:
            record: The SessionRecord to save. Atomically replaces any prior
                   version with the same session_id.
        """
        ...

    def delete(self, session_id: str) -> None:
        """Delete a session by ID.

        Args:
            session_id: The session identifier.
        """
        ...

    def purge_expired(self) -> int:
        """Remove all expired sessions.

        Returns:
            The count of sessions deleted.
        """
        ...
