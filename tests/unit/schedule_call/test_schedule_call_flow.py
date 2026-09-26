"""Schedule-call flow branches as they surface in a chat turn."""

from __future__ import annotations

import pytest

from application.tasks.schedule_call.workflow import ScheduleCallWorkflow
from application.use_cases.handle_user_message import HandleUserMessageUseCase
from domain.enums.workflow_state import WorkflowState
from domain.exceptions import DomainError
from DTO.inputs.chat import ChatRequest
from DTO.outputs.chat import ChatResponse
from models.inputs.response import ResponseWording
from ports.session_store import SessionStore
from tests.fakes import (
    FakeLLM,
    StubCarRepository,
    StubDealerRepository,
    StubScheduleRepository,
    schedule_extraction,
    task_decision,
    wording_reply,
)

pytestmark = pytest.mark.unit


def _service(
    llm: FakeLLM,
    session_store: SessionStore,
    schedule_repo: StubScheduleRepository | None = None,
) -> HandleUserMessageUseCase:
    """Compose the turn handler under test.

    Args:
        llm: Scripted LLM port.
        session_store: Session store fixture.
        schedule_repo: Optional schedule repository stub.

    Returns:
        The turn handler.
    """
    return HandleUserMessageUseCase(
        session_store,
        llm,
        StubCarRepository(),
        StubDealerRepository(),
        schedule_repo or StubScheduleRepository(),
    )


def _booking_session(session_store: SessionStore) -> str:
    """Create a session that has a car and dealer selected.

    Args:
        session_store: Session store fixture.

    Returns:
        The new session id.
    """
    record = session_store.create(user_id="u-1")
    record.selected_car_id = "C-0003"
    record.selected_dealer_id = "D-003"
    record.workflow_state = "AWAITING_ACTION"
    session_store.save(record)
    return record.session_id


def _schedule_turn(
    service: HandleUserMessageUseCase, session_id: str, message: str
) -> ChatResponse:
    """Run one scheduling turn.

    Args:
        service: The turn handler.
        session_id: Session to continue.
        message: The user message.

    Returns:
        The ChatResponse.
    """
    return service.execute(ChatRequest(session_id=session_id, message=message))


class TestScheduleCallWorkflowStates:
    """ScheduleCallWorkflow.advance: both branches."""

    def test_created_advances_to_schedule_confirmed(self) -> None:
        """A persisted schedule lands on SCHEDULE_CONFIRMED."""
        assert ScheduleCallWorkflow.advance(schedule_created=True) is (
            WorkflowState.SCHEDULE_CONFIRMED
        )

    def test_not_created_stays_awaiting_datetime(self) -> None:
        """Any question keeps the session collecting date/time."""
        assert ScheduleCallWorkflow.advance(schedule_created=False) is (
            WorkflowState.AWAITING_DATETIME
        )


class TestScheduleCallTurnBranches:
    """Turn-level branches: create, ask, clarify, reject, guard."""

    def test_full_scheduling_turn_persists_and_confirms(self, session_store: SessionStore) -> None:
        """Happy path: date + time + timezone creates and persists a record."""
        llm = FakeLLM()
        llm.enqueue(task_decision("SCHEDULE_CALL"))
        llm.enqueue(schedule_extraction("2030-05-15", "15:00", "UTC"))
        llm.enqueue(wording_reply("Booked for May 15, 2030 at 15:00 UTC."))
        schedule_repo = StubScheduleRepository()
        session_id = _booking_session(session_store)

        response = _schedule_turn(
            _service(llm, session_store, schedule_repo),
            session_id,
            "book a call on 2030-05-15 at 3pm UTC",
        )

        assert response.reply == "Booked for May 15, 2030 at 15:00 UTC."
        assert response.workflow_state == "SCHEDULE_CONFIRMED"
        assert response.suggested_actions == ["Find another car", "Get dealer details"]
        assert len(schedule_repo.saved) == 1

    def test_missing_fields_ask_and_carry_context_across_turns(
        self, session_store: SessionStore
    ) -> None:
        """Edge: missing date/time asks only for what is missing, then completes."""
        llm = FakeLLM()
        llm.enqueue(task_decision("SCHEDULE_CALL"))
        llm.enqueue(schedule_extraction(None, "15:00"))
        llm.enqueue(task_decision("SCHEDULE_CALL"))
        llm.enqueue(schedule_extraction("tomorrow", None))
        llm.enqueue(ResponseWording(reply=""))
        session_id = _booking_session(session_store)
        service = _service(llm, session_store)

        first = _schedule_turn(service, session_id, "at 3pm")
        assert "What date" in first.reply
        assert first.workflow_state == "AWAITING_DATETIME"

        second = _schedule_turn(service, session_id, "tomorrow")
        assert second.workflow_state == "SCHEDULE_CONFIRMED"
        assert second.reply.startswith("Your call is booked for")

    def test_ambiguous_time_clarifies(self, session_store: SessionStore) -> None:
        """Edge: an ambiguous time is clarified, never guessed."""
        llm = FakeLLM()
        llm.enqueue(task_decision("SCHEDULE_CALL"))
        llm.enqueue(schedule_extraction("Friday", "3"))
        session_id = _booking_session(session_store)

        response = _schedule_turn(_service(llm, session_store), session_id, "Friday at 3")

        assert "morning or in the afternoon" in response.reply
        assert response.workflow_state == "AWAITING_DATETIME"

    def test_past_time_is_rejected(self, session_store: SessionStore) -> None:
        """Edge: a past date/time is rejected before any persistence."""
        llm = FakeLLM()
        llm.enqueue(task_decision("SCHEDULE_CALL"))
        llm.enqueue(schedule_extraction("2020-01-01", "10am"))
        schedule_repo = StubScheduleRepository()
        session_id = _booking_session(session_store)

        response = _schedule_turn(
            _service(llm, session_store, schedule_repo), session_id, "2020-01-01 at 10am"
        )

        assert "already passed" in response.reply
        assert response.workflow_state == "AWAITING_DATETIME"
        assert schedule_repo.saved == []

    def test_user_cancels_scheduling(self, session_store: SessionStore) -> None:
        """Edge: a cancellation is answered gracefully and books nothing."""
        llm = FakeLLM()
        llm.enqueue(task_decision("UNKNOWN"))
        schedule_repo = StubScheduleRepository()
        session_id = _booking_session(session_store)

        response = _schedule_turn(
            _service(llm, session_store, schedule_repo), session_id, "never mind, cancel that"
        )

        assert response.reply.startswith("I didn't understand that.")
        assert schedule_repo.saved == []
        assert response.workflow_state == "AWAITING_ACTION"

    def test_schedule_without_dealer_is_refused(self, session_store: SessionStore) -> None:
        """Guard branch: no dealer selected → ask to pick a car first."""
        llm = FakeLLM()
        llm.enqueue(task_decision("SCHEDULE_CALL"))
        record = session_store.create(user_id="u-1")
        record.workflow_state = "CAR_SELECTED"
        session_store.save(record)

        response = _schedule_turn(
            _service(llm, session_store), record.session_id, "schedule a call"
        )

        assert response.reply == "No dealer selected. Please search for and select a car first."
        assert response.workflow_state == "CAR_SELECTED"

    def test_persistence_failure_is_reported_not_raised(self, session_store: SessionStore) -> None:
        """Failure branch: a repository error becomes a retry question."""
        llm = FakeLLM()
        llm.enqueue(task_decision("SCHEDULE_CALL"))
        llm.enqueue(schedule_extraction("2030-05-15", "15:00"))

        session_id = _booking_session(session_store)
        service = _service(
            llm, session_store, StubScheduleRepository(error=DomainError("write failed"))
        )

        response = _schedule_turn(service, session_id, "2030-05-15 at 3pm")

        assert "could not save it" in response.reply
        assert response.workflow_state == "AWAITING_DATETIME"
