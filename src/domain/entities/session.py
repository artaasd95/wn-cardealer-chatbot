from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from domain.entities.message import Message
from domain.enums.workflow_state import LEGAL_TRANSITIONS, WorkflowState, ensure_legal_transition

"""Session domain entity with state machine."""


@dataclass
class Session:
    """Domain entity representing a user session with state machine."""

    session_id: str
    user_id: str | None
    workflow_state: WorkflowState
    conversation_history: list[Message] = field(default_factory=list)
    selected_car_id: str | None = None
    selected_dealer_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
    expires_at: datetime | None = None

    # The legal-transition table lives in domain.enums.workflow_state so the
    # domain entity and the application layer validate against one source.
    _LEGAL_TRANSITIONS = LEGAL_TRANSITIONS

    def advance_to(self, new_state: WorkflowState) -> None:
        """Advance to a new state if the transition is legal.

        Args:
            new_state: Target workflow state.

        Raises:
            InvalidTransitionError: If the transition is not legal, or if
                COMPLETE is requested before a car and a dealer are confirmed.
        """
        ensure_legal_transition(
            self.workflow_state,
            new_state,
            selected_car_id=self.selected_car_id,
            selected_dealer_id=self.selected_dealer_id,
        )
        self.workflow_state = new_state
        self.updated_at = datetime.now(UTC).replace(tzinfo=None)

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history.

        Args:
            role: 'user' or 'assistant'.
            content: Message text.
        """
        msg = Message(role=role, content=content)
        self.conversation_history.append(msg)
        self.updated_at = datetime.now(UTC).replace(tzinfo=None)

    def last_user_message(self) -> str | None:
        """Get the content of the last user message.

        Returns:
            Content of the most recent user message, or None if not found.
        """
        for msg in reversed(self.conversation_history):
            if msg.is_user_message():
                return msg.content
        return None

    def last_assistant_message(self) -> str | None:
        """Get the content of the last assistant message.

        Returns:
            Content of the most recent assistant message, or None if not found.
        """
        for msg in reversed(self.conversation_history):
            if msg.is_assistant_message():
                return msg.content
        return None

    def is_expired(self) -> bool:
        """Check if the session has expired.

        Returns:
            True if expires_at is set and in the past.
        """
        if not self.expires_at:
            return False
        return self.expires_at < datetime.now(UTC).replace(tzinfo=None)

    def reset_to_start(self) -> None:
        """Reset the session to START state, clearing selections.

        Clears selected car and dealer, resets to START state,
        but preserves conversation history.
        """
        self.workflow_state = WorkflowState.START
        self.selected_car_id = None
        self.selected_dealer_id = None
        self.updated_at = datetime.now(UTC).replace(tzinfo=None)

    def is_complete(self) -> bool:
        """Check if the session has completed a full flow.

        Returns:
            True if workflow_state is COMPLETE.
        """
        return self.workflow_state == WorkflowState.COMPLETE
