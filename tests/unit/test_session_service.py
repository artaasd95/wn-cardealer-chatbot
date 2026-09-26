"""Tests for application/session/service.py."""

from __future__ import annotations

import pytest

from application.session.service import SessionService
from domain.enums.workflow_state import WorkflowState
from domain.exceptions import DomainError
from ports.session_store import SessionStore


class TestSessionService:
    """Tests for SessionService."""

    def test_get_or_create_new_session(self, session_store: SessionStore) -> None:
        """Test creating a new session."""
        service = SessionService(session_store)
        session = service.get_or_create(session_id=None, user_id="user-1")

        assert session.session_id is not None
        assert session.workflow_state == WorkflowState.START.value
        assert session.conversation_history == []

    def test_get_or_create_existing_session(self, session_store: SessionStore) -> None:
        """Test retrieving an existing session."""
        service = SessionService(session_store)

        # Create first
        session1 = service.get_or_create(session_id=None, user_id="user-1")

        # Retrieve using same ID
        session2 = service.get_or_create(session_id=session1.session_id)

        assert session2.session_id == session1.session_id

    def test_persist_session(self, session_store: SessionStore) -> None:
        """Test persisting a session."""
        service = SessionService(session_store)
        session = service.get_or_create(session_id=None)

        # Modify and persist
        session.workflow_state = WorkflowState.CAR_SELECTED.value
        service.persist(session)

        # Retrieve and verify
        retrieved = session_store.get(session.session_id)
        assert retrieved.workflow_state == WorkflowState.CAR_SELECTED.value

    def test_require_selected_car_success(self, session_store: SessionStore) -> None:
        """Test that require_selected_car returns car ID when set."""
        service = SessionService(session_store)
        session = service.get_or_create(session_id=None)
        session.selected_car_id = "car-123"

        car_id = service.require_selected_car(session)
        assert car_id == "car-123"

    def test_require_selected_car_failure(self, session_store: SessionStore) -> None:
        """Test that require_selected_car raises when not set."""
        service = SessionService(session_store)
        session = service.get_or_create(session_id=None)

        with pytest.raises(DomainError, match="No car selected"):
            service.require_selected_car(session)

    def test_require_selected_dealer_success(self, session_store: SessionStore) -> None:
        """Test that require_selected_dealer returns dealer ID when set."""
        service = SessionService(session_store)
        session = service.get_or_create(session_id=None)
        session.selected_dealer_id = "dealer-123"

        dealer_id = service.require_selected_dealer(session)
        assert dealer_id == "dealer-123"

    def test_require_selected_dealer_failure(self, session_store: SessionStore) -> None:
        """Test that require_selected_dealer raises when not set."""
        service = SessionService(session_store)
        session = service.get_or_create(session_id=None)

        with pytest.raises(DomainError, match="No dealer selected"):
            service.require_selected_dealer(session)

    def test_append_message(self, session_store: SessionStore) -> None:
        """Test appending a message to history."""
        service = SessionService(session_store)
        session = service.get_or_create(session_id=None)

        session = service.append_message(session, "user", "Hello")

        assert len(session.conversation_history) == 1
        assert session.conversation_history[0].role == "user"
        assert session.conversation_history[0].content == "Hello"

    def test_append_message_caps_history(self, session_store: SessionStore) -> None:
        """Test that message history is capped at 100."""
        service = SessionService(session_store)
        session = service.get_or_create(session_id=None)

        # Add 150 messages
        for i in range(150):
            session = service.append_message(session, "user", f"Message {i}")

        # Should only keep last 100
        assert len(session.conversation_history) == 100
        assert session.conversation_history[0].content == "Message 50"

    def test_reset_session(self, session_store: SessionStore) -> None:
        """Test resetting a session to START state."""
        service = SessionService(session_store)
        session = service.get_or_create(session_id=None)

        # Set some state
        session.workflow_state = WorkflowState.CAR_SELECTED.value
        session.selected_car_id = "car-123"
        session = service.append_message(session, "user", "Hi")

        # Reset
        session = service.reset(session)

        assert session.workflow_state == WorkflowState.START.value
        assert session.selected_car_id is None
        assert session.selected_dealer_id is None
        assert session.conversation_history == []

    def test_advance_workflow(self, session_store: SessionStore) -> None:
        """Test advancing workflow state."""
        service = SessionService(session_store)
        session = service.get_or_create(session_id=None)

        session = service.advance_workflow(session, WorkflowState.CAR_SELECTED)

        assert session.workflow_state == WorkflowState.CAR_SELECTED.value

    def test_set_selected_car(self, session_store: SessionStore) -> None:
        """Test setting selected car."""
        service = SessionService(session_store)
        session = service.get_or_create(session_id=None)

        session = service.set_selected_car(session, "car-456")

        assert session.selected_car_id == "car-456"

    def test_set_selected_dealer(self, session_store: SessionStore) -> None:
        """Test setting selected dealer."""
        service = SessionService(session_store)
        session = service.get_or_create(session_id=None)

        session = service.set_selected_dealer(session, "dealer-789")

        assert session.selected_dealer_id == "dealer-789"

    def test_set_scheduling_context(self, session_store: SessionStore) -> None:
        """Test setting scheduling context."""
        service = SessionService(session_store)
        session = service.get_or_create(session_id=None)

        context = {"date": "2026-10-01", "time": "14:00"}
        session = service.set_scheduling_context(session, context)

        assert session.scheduling_context == context

    def test_add_seen_car_appends(self, session_store: SessionStore) -> None:
        """A newly seen car is recorded on the session."""
        service = SessionService(session_store)
        session = service.get_or_create(session_id=None)

        session = service.add_seen_car(session, "C-1", "BMW", "3 Series", "320i", 2021)

        assert len(session.seen_cars) == 1
        assert session.seen_cars[0] == {
            "car_id": "C-1",
            "make": "BMW",
            "model": "3 Series",
            "variant": "320i",
            "year": 2021,
        }

    def test_add_seen_car_deduplicates(self, session_store: SessionStore) -> None:
        """The same car is not recorded twice."""
        service = SessionService(session_store)
        session = service.get_or_create(session_id=None)

        session = service.add_seen_car(session, "C-1", "BMW", "3 Series", "320i", 2021)
        session = service.add_seen_car(session, "C-1", "BMW", "3 Series", "320i", 2021)
        session = service.add_seen_car(session, "C-2", "Honda", "City", None, 2020)

        assert [c["car_id"] for c in session.seen_cars] == ["C-1", "C-2"]

    def test_add_seen_car_persists(self, session_store: SessionStore) -> None:
        """Seen cars survive the persist round trip."""
        service = SessionService(session_store)
        session = service.get_or_create(session_id=None)
        session = service.add_seen_car(session, "C-1", "BMW", "3 Series", "320i", 2021)

        service.persist(session)

        stored = session_store.get(session.session_id)
        assert stored is not None
        assert stored.seen_cars == [
            {"car_id": "C-1", "make": "BMW", "model": "3 Series", "variant": "320i", "year": 2021}
        ]

    def test_seen_cars_default_empty(self, session_store: SessionStore) -> None:
        """A fresh session starts with no seen cars."""
        service = SessionService(session_store)
        session = service.get_or_create(session_id=None)

        assert session.seen_cars == []
