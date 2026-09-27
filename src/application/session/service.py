"""Session service facade.

Coordinates session operations: creation, retrieval, persistence, and state management.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from application.use_cases.load_session import LoadSessionUseCase
from application.use_cases.save_session import SaveSessionUseCase
from domain.enums.workflow_state import (
    WorkflowState,
    ensure_legal_transition,
    shortest_legal_path,
)
from domain.exceptions import DomainError, InvalidTransitionError
from DTO.inputs.session import SessionRequest
from models.outputs.message import MessageRecord
from models.outputs.session import SessionRecord
from ports.session_store import SessionStore

logger = logging.getLogger(__name__)

# Fallback TTL for stores that return a snapshot without an expiry; matches the
# default of SessionStore.create().
_DEFAULT_TTL_SECONDS = 3600


class SessionService:
    """Facade for session management."""

    def __init__(self, session_store: SessionStore) -> None:
        """Initialize the facade over the session use cases.

        Args:
            session_store: SessionStore port for persistence.
        """
        self.session_store = session_store
        self.load_session = LoadSessionUseCase(session_store)
        self.save_session = SaveSessionUseCase(session_store)

    def get_or_create(self, session_id: str | None, user_id: str | None = None) -> SessionRecord:
        """Get an existing session or create a new one.

        Delegates loading/creating to LoadSessionUseCase, then rebuilds the
        mutable record the turn needs.

        Args:
            session_id: Optional session ID to load.
            user_id: Optional user ID for new sessions.

        Returns:
            A SessionRecord (loaded or newly created).
        """
        snapshot = self.load_session.execute(
            SessionRequest(session_id=session_id or "", user_id=user_id)
        )
        # Rebuild the mutable record the turn works on. The TTL and the
        # scheduling context must survive the round trip, otherwise the session
        # would expire one turn later and partially collected date/time would
        # be lost. This covers both branches of the load use case: a session it
        # found, and one it just created.
        return SessionRecord(
            session_id=snapshot.session_id,
            user_id=snapshot.user_id,
            workflow_state=snapshot.workflow_state,
            selected_car_id=snapshot.selected_car_id,
            selected_dealer_id=snapshot.selected_dealer_id,
            conversation_history=snapshot.conversation_history,
            scheduling_context=snapshot.scheduling_context,
            seen_cars=snapshot.seen_cars,
            pending_disambiguation=snapshot.pending_disambiguation,
            expires_at=snapshot.expires_at
            or (datetime.now(UTC) + timedelta(seconds=_DEFAULT_TTL_SECONDS)),
        )

    def persist(self, record: SessionRecord) -> None:
        """Persist a session record.

        Delegates to SaveSessionUseCase.

        Args:
            record: The SessionRecord to save.
        """
        self.save_session.execute(record)

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
            created_at=datetime.now(UTC),
        )

        record.conversation_history.append(message)

        # Cap history length to avoid unbounded growth
        max_history = 100
        if len(record.conversation_history) > max_history:
            record.conversation_history = record.conversation_history[-max_history:]

        return record

    def set_pending_disambiguation(
        self, record: SessionRecord, candidates: list[dict]
    ) -> SessionRecord:
        """Store the list of candidate cars for a disambiguation prompt.

        Args:
            record: Current session.
            candidates: List of car dicts with car_id, make, model, variant, year.

        Returns:
            Updated SessionRecord.
        """
        record.pending_disambiguation = candidates
        record.updated_at = datetime.now(UTC)
        return record

    def resolve_disambiguation(
        self, record: SessionRecord, user_text: str
    ) -> tuple[dict | None, int | None]:
        """Try to resolve a positional reference against pending candidates.

        Recognises patterns like "second option", "option 2", "the first one",
        "3", "number three", etc.

        Returns:
            Tuple of (matched candidate dict, 1-based index) or (None, None).
        """
        import re

        if not record.pending_disambiguation:
            return None, None

        text = user_text.strip().lower()
        n = len(record.pending_disambiguation)

        # Word→number map
        _words = {
            "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
            "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        }

        idx: int | None = None

        # "option N", "option Nth", "pick N", "number N"
        m = re.search(r"(?:option|pick|number|#)\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten|first|second|third|fourth|fifth)", text)
        if m:
            token = m.group(1)
            idx = _words.get(token) or (int(token) if token.isdigit() else None)

        # "Nth option" / "N option"
        if idx is None:
            m = re.search(r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten|first|second|third|fourth|fifth)\s*(?:option|one)?", text)
            if m:
                token = m.group(1)
                idx = _words.get(token) or (int(token) if token.isdigit() else None)

        # Bare number
        if idx is None and text.isdigit():
            idx = int(text)

        if idx is not None and 1 <= idx <= n:
            return record.pending_disambiguation[idx - 1], idx

        return None, None

    def clear_pending_disambiguation(self, record: SessionRecord) -> SessionRecord:
        """Clear the pending disambiguation list after a selection is made."""
        record.pending_disambiguation = []
        record.updated_at = datetime.now(UTC)
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
        record.pending_disambiguation = []
        record.conversation_history = []
        record.updated_at = datetime.now(UTC)

        logger.info(f"Session {record.session_id} reset to START state")
        return record

    def advance_workflow(self, record: SessionRecord, new_state: WorkflowState) -> SessionRecord:
        """Advance the workflow to a new state.

        Validates the move against the domain state machine, so application
        code can only step along a legal edge and can only reach COMPLETE once
        a car and a dealer have been confirmed by a repository call.

        Args:
            record: The current session record.
            new_state: The target workflow state.

        Returns:
            Updated SessionRecord with the new state.

        Raises:
            InvalidTransitionError: If the transition is not legal.
        """
        ensure_legal_transition(
            WorkflowState(record.workflow_state),
            new_state,
            selected_car_id=record.selected_car_id,
            selected_dealer_id=record.selected_dealer_id,
        )
        record.workflow_state = new_state.value
        record.updated_at = datetime.now(UTC)
        return record

    def advance_through(self, record: SessionRecord, target: WorkflowState) -> SessionRecord:
        """Advance to a target state along the shortest chain of legal edges.

        A single turn can legitimately pass through intermediate states
        (CAR_SELECTED → AWAITING_ACTION, AWAITING_ACTION → …) exactly as the
        plan's state diagram shows; every edge on the path is validated, and
        the COMPLETE gate still applies at the moment it is crossed.

        Args:
            record: The current session record.
            target: The state to reach.

        Returns:
            Updated SessionRecord in the target state.

        Raises:
            InvalidTransitionError: If no legal path exists (or the COMPLETE
                gate rejects the final step).
        """
        current = WorkflowState(record.workflow_state)
        path = shortest_legal_path(current, target)
        if path is None:
            raise InvalidTransitionError(
                from_state=current.value,
                to_state=target.value,
                reason="no legal path in state machine",
            )
        for step in path[1:]:
            record = self.advance_workflow(record, step)
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
        record.updated_at = datetime.now(UTC)
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
        record.updated_at = datetime.now(UTC)
        return record

    def set_scheduling_context(
        self, record: SessionRecord, context: dict[str, str | None]
    ) -> SessionRecord:
        """Update the scheduling context.

        Args:
            record: The current session record.
            context: The scheduling context dict.

        Returns:
            Updated SessionRecord.
        """
        record.scheduling_context = context
        record.updated_at = datetime.now(UTC)
        return record

    def add_seen_car(
        self,
        record: SessionRecord,
        car_id: str,
        make: str,
        model: str,
        variant: str | None,
        year: int | None,
    ) -> SessionRecord:
        """Append a car to the session's seen-cars list (deduplicates by car_id).

        Args:
            record: The current session record.
            car_id: Unique car identifier.
            make: Car make (e.g. Toyota).
            model: Car model (e.g. Camry).
            variant: Optional trim/variant string.
            year: Model year.

        Returns:
            Updated SessionRecord.
        """
        if not any(c.get("car_id") == car_id for c in record.seen_cars):
            record.seen_cars.append(
                {"car_id": car_id, "make": make, "model": model, "variant": variant, "year": year}
            )
            record.updated_at = datetime.now(UTC)
        return record
