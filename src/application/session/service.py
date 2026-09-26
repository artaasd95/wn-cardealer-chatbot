"""Session service facade.

Coordinates session operations: creation, retrieval, persistence, and state management.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

from domain.enums.workflow_state import WorkflowState
from domain.exceptions import DomainError
from models.outputs.session import MessageRecord, SessionRecord
from ports.session_store import SessionStore

logger = logging.getLogger(__name__)


class SessionService:
    """Facade for session management."""

    def __init__(self, session_store: SessionStore) -> None:
        """Initialize with session store dependency.

        Args:
            session_store: SessionStore port for persistence.
        """
        self.session_store = session_store

    def get_or_create(self, session_id: str | None, user_id: str | None = None) -> SessionRecord:
        """Get an existing session or create a new one.

        Args:
            session_id: Optional session ID to load.
            user_id: Optional user ID for new sessions.

        Returns:
            A SessionRecord (loaded or newly created).
        """
        if session_id:
            snapshot = self.session_store.get(session_id)
            if snapshot:
                # Reconstruct full SessionRecord from snapshot
                return SessionRecord(
                    session_id=snapshot.session_id,
                    user_id=None,  # Not stored in snapshot
                    workflow_state=snapshot.workflow_state,
                    selected_car_id=snapshot.selected_car_id,
                    selected_dealer_id=snapshot.selected_dealer_id,
                    conversation_history=snapshot.conversation_history,
                    scheduling_context=snapshot.scheduling_context,
                    expires_at=datetime.utcnow(),  # Placeholder
                    created_at=datetime.utcnow(),  # Placeholder
                    updated_at=datetime.utcnow(),
                )

        # Create new
        record = self.session_store.create(user_id=user_id)
        return record

    def persist(self, record: SessionRecord) -> None:
        """Persist a session record.

        Args:
            record: The SessionRecord to save.
        """
        self.session_store.save(record)

    def require_selected_car(self, record: SessionRecord) -> str:
        """Guard: ensure a car is selected.

        Args:
            record: The current session record.

        Returns:
            The selected car ID.

        Raises:
            DomainError: If no car is selected.
        """
        if not record.selected_car_id:
            raise DomainError("No car selected. Please search for and select a car first.")
        return record.selected_car_id

    def require_selected_dealer(self, record: SessionRecord) -> str:
        """Guard: ensure a dealer is selected.

        Args:
            record: The current session record.

        Returns:
            The selected dealer ID.

        Raises:
            DomainError: If no dealer is selected.
        """
        if not record.selected_dealer_id:
            raise DomainError("No dealer selected. Please search for and select a car first.")
        return record.selected_dealer_id

    def is_expired(self, session_id: str) -> bool:
        """Check if a session has expired.

        Args:
            session_id: The session ID to check.

        Returns:
            True if expired, False otherwise.
        """
        return self.session_store.get(session_id) is None

    def append_message(self, record: SessionRecord, role: str, content: str) -> SessionRecord:
        """Append a message to the conversation history.

        Args:
            record: The current session record.
            role: Message role ("user" or "assistant").
            content: Message content.

        Returns:
            Updated SessionRecord with the message appended.
        """
        message = MessageRecord(
            message_id=str(uuid4()),
            role=role,
            content=content,
            created_at=datetime.utcnow(),
        )

        record.conversation_history.append(message)

        # Cap history length to avoid unbounded growth
        max_history = 100
        if len(record.conversation_history) > max_history:
            record.conversation_history = record.conversation_history[-max_history:]

        return record

    def reset(self, record: SessionRecord) -> SessionRecord:
        """Reset a session to the START state (restart conversation).

        Args:
            record: The current session record.

        Returns:
            Updated SessionRecord at START state with cleared selections.
        """
        record.workflow_state = WorkflowState.START.value
        record.selected_car_id = None
        record.selected_dealer_id = None
        record.conversation_history = []
        record.scheduling_context = {}
        record.updated_at = datetime.utcnow()

        logger.info(f"Session {record.session_id} reset to START state")
        return record

    def advance_workflow(self, record: SessionRecord, new_state: WorkflowState) -> SessionRecord:
        """Advance the workflow to a new state.

        Args:
            record: The current session record.
            new_state: The target workflow state.

        Returns:
            Updated SessionRecord with the new state.
        """
        record.workflow_state = new_state.value
        record.updated_at = datetime.utcnow()
        return record

    def set_selected_car(self, record: SessionRecord, car_id: str) -> SessionRecord:
        """Set the selected car.

        Args:
            record: The current session record.
            car_id: The car ID to select.

        Returns:
            Updated SessionRecord.
        """
        record.selected_car_id = car_id
        record.updated_at = datetime.utcnow()
        return record

    def set_selected_dealer(self, record: SessionRecord, dealer_id: str) -> SessionRecord:
        """Set the selected dealer.

        Args:
            record: The current session record.
            dealer_id: The dealer ID to select.

        Returns:
            Updated SessionRecord.
        """
        record.selected_dealer_id = dealer_id
        record.updated_at = datetime.utcnow()
        return record

    def set_scheduling_context(self, record: SessionRecord, context: dict) -> SessionRecord:
        """Update the scheduling context.

        Args:
            record: The current session record.
            context: The scheduling context dict.

        Returns:
            Updated SessionRecord.
        """
        record.scheduling_context = context
        record.updated_at = datetime.utcnow()
        return record
