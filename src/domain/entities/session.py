from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from domain.entities.message import Message
from domain.enums.workflow_state import WorkflowState
from domain.exceptions import InvalidTransitionError

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
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None

    # State machine: defines legal transitions
    _LEGAL_TRANSITIONS = {
        WorkflowState.START: {
            WorkflowState.AWAITING_CAR,
        },
        WorkflowState.AWAITING_CAR: {
            WorkflowState.CAR_SELECTED,
            WorkflowState.CAR_NOT_FOUND,
            WorkflowState.START,
        },
        WorkflowState.CAR_SELECTED: {
            WorkflowState.AWAITING_ACTION,
            WorkflowState.AWAITING_CAR,
            WorkflowState.START,
        },
        WorkflowState.CAR_NOT_FOUND: {
            WorkflowState.AWAITING_CAR,
            WorkflowState.START,
        },
        WorkflowState.AWAITING_ACTION: {
            WorkflowState.AWAITING_DEALER_DETAILS,
            WorkflowState.AWAITING_DATETIME,
            WorkflowState.AWAITING_CAR,
            WorkflowState.START,
        },
        WorkflowState.AWAITING_DEALER_DETAILS: {
            WorkflowState.DEALER_DETAILS_SHOWN,
            WorkflowState.START,
        },
        WorkflowState.DEALER_DETAILS_SHOWN: {
            WorkflowState.AWAITING_DATETIME,
            WorkflowState.AWAITING_CAR,
            WorkflowState.START,
        },
        WorkflowState.AWAITING_DATETIME: {
            WorkflowState.SCHEDULE_CONFIRMED,
            WorkflowState.AWAITING_ACTION,
            WorkflowState.START,
        },
        WorkflowState.SCHEDULE_CONFIRMED: {
            WorkflowState.COMPLETE,
            WorkflowState.AWAITING_CAR,
            WorkflowState.START,
        },
        WorkflowState.COMPLETE: {
            WorkflowState.START,
        },
    }

    def advance_to(self, new_state: WorkflowState) -> None:
        """Advance to a new state if the transition is legal.

        Args:
            new_state: Target workflow state.

        Raises:
            InvalidTransitionError: If the transition is not legal.
        """
        if new_state not in self._LEGAL_TRANSITIONS.get(self.workflow_state, set()):
            raise InvalidTransitionError(
                from_state=self.workflow_state.value,
                to_state=new_state.value,
                reason="transition not defined in state machine",
            )
        self.workflow_state = new_state
        self.updated_at = datetime.utcnow()

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history.

        Args:
            role: 'user' or 'assistant'.
            content: Message text.
        """
        msg = Message(role=role, content=content)
        self.conversation_history.append(msg)
        self.updated_at = datetime.utcnow()

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
        return self.expires_at < datetime.utcnow()

    def reset_to_start(self) -> None:
        """Reset the session to START state, clearing selections.

        Clears selected car and dealer, resets to START state,
        but preserves conversation history.
        """
        self.workflow_state = WorkflowState.START
        self.selected_car_id = None
        self.selected_dealer_id = None
        self.updated_at = datetime.utcnow()

    def is_complete(self) -> bool:
        """Check if the session has completed a full flow.

        Returns:
            True if workflow_state is COMPLETE.
        """
        return self.workflow_state == WorkflowState.COMPLETE
