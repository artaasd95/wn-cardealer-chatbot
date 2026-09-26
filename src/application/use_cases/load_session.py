"""Load session use case.

Retrieves an existing session or creates a new one if it doesn't exist.
"""

from __future__ import annotations

from DTO.inputs.session import SessionRequest
from models.outputs.session import SessionSnapshotRecord
from ports.session_store import SessionStore


class LoadSessionUseCase:
    """Load or create a session."""

    def __init__(self, session_store: SessionStore) -> None:
        """Initialize with session store dependency.

        Args:
            session_store: SessionStore port for persistence.
        """
        self.session_store = session_store

    def execute(self, request: SessionRequest) -> SessionSnapshotRecord:
        """Load a session or create a new one.

        Args:
            request: SessionRequest with session_id (may be empty on a first
                turn) and an optional user_id.

        Returns:
            SessionSnapshotRecord containing the loaded or newly created
            session, including its user, TTL and scheduling context so the
            caller can round-trip it without losing state.
        """
        if request.session_id:
            existing = self.session_store.get(request.session_id)
            if existing:
                return existing

        # Create new session
        record = self.session_store.create(user_id=request.user_id)
        return SessionSnapshotRecord(
            session_id=record.session_id,
            user_id=record.user_id,
            workflow_state=record.workflow_state,
            selected_car_id=record.selected_car_id,
            selected_dealer_id=record.selected_dealer_id,
            conversation_history=record.conversation_history,
            scheduling_context=record.scheduling_context,
            expires_at=record.expires_at,
        )
