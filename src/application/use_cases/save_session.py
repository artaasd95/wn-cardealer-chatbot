"""Save session use case.

Persists a session record to the session store.
"""

from __future__ import annotations

from models.outputs.session import SessionRecord
from ports.session_store import SessionStore


class SaveSessionUseCase:
    """Save a session to the store."""

    def __init__(self, session_store: SessionStore) -> None:
        """Initialize with session store dependency.

        Args:
            session_store: SessionStore port for persistence.
        """
        self.session_store = session_store

    def execute(self, record: SessionRecord) -> None:
        """Persist a session record.

        Args:
            record: The SessionRecord to save.
        """
        self.session_store.save(record)
