"""Dealer-details flow branches (plan Phase 8: one test per flow branch)."""

from __future__ import annotations

import pytest

from application.tasks.dealer_details.workflow import DealerDetailsWorkflow
from application.use_cases.handle_user_message import HandleUserMessageUseCase
from domain.enums.workflow_state import WorkflowState
from DTO.inputs.chat import ChatRequest
from models.inputs.response import ResponseWording
from models.inputs.task import TaskDecision
from ports.session_store import SessionStore
from tests.fakes import (
    FakeLLM,
    StubCarRepository,
    StubDealerRepository,
    make_dealer,
    task_decision,
    wording_reply,
)

pytestmark = pytest.mark.unit


def _service(
    llm: FakeLLM,
    session_store: SessionStore,
    dealer_repo: StubDealerRepository,
) -> HandleUserMessageUseCase:
    """Compose the turn handler under test.

    Args:
        llm: Scripted LLM port.
        session_store: Session store fixture.
        dealer_repo: Dealer repository stub.

    Returns:
        The turn handler.
    """
    return HandleUserMessageUseCase(session_store, llm, StubCarRepository(), dealer_repo)


def _selected_session(
    session_store: SessionStore,
    *,
    car_id: str | None = "C-0003",
    dealer_id: str | None = "D-003",
    state: str = "AWAITING_ACTION",
) -> str:
    """Create a session with a stored selection.

    Args:
        session_store: Session store fixture.
        car_id: Selected car id, or None.
        dealer_id: Selected dealer id, or None.
        state: Workflow state to start from.

    Returns:
        The new session id.
    """
    record = session_store.create(user_id="u-1")
    record.selected_car_id = car_id
    record.selected_dealer_id = dealer_id
    record.workflow_state = state
    session_store.save(record)
    return record.session_id


class TestDealerDetailsWorkflowStates:
    """DealerDetailsWorkflow.advance: both branches."""

    def test_dealer_found_advances_to_shown(self) -> None:
        """A confirmed dealer row lands on DEALER_DETAILS_SHOWN."""
        assert DealerDetailsWorkflow.advance(dealer_found=True) is (
            WorkflowState.DEALER_DETAILS_SHOWN
        )

    def test_dealer_missing_stays_on_awaiting_action(self) -> None:
        """No dealer row: stay put so the user can pick a car."""
        assert DealerDetailsWorkflow.advance(dealer_found=False) is WorkflowState.AWAITING_ACTION


class TestDealerDetailsBranches:
    """Happy path, partial row, missing dealer and the selection guard."""

    def test_details_are_worded_through_the_llm(self, session_store: SessionStore) -> None:
        """Happy path: the LLM words the details built from the record."""
        llm = FakeLLM()
        llm.enqueue(task_decision("DEALER_DETAILS"))
        llm.enqueue(wording_reply("Prestige Cars sits at 78 MG Road, Bangalore. Call +91-80-2552-1003."))
        dealer_repo = StubDealerRepository(by_id={"D-003": make_dealer("D-003")})
        session_id = _selected_session(session_store)

        response = _service(llm, session_store, dealer_repo).execute(
            ChatRequest(session_id=session_id, message="show me the dealer details")
        )

        assert response.reply == (
            "Prestige Cars sits at 78 MG Road, Bangalore. Call +91-80-2552-1003."
        )
        assert response.workflow_state == "DEALER_DETAILS_SHOWN"
        assert response.suggested_actions == ["Schedule a call", "Find another car"]

    def test_empty_llm_wording_falls_back_to_deterministic_details(
        self, session_store: SessionStore
    ) -> None:
        """Failure branch: a dead provider still shows every detail."""
        llm = FakeLLM()
        llm.enqueue(task_decision("DEALER_DETAILS"))
        llm.enqueue(ResponseWording(reply=""))
        dealer_repo = StubDealerRepository(by_id={"D-003": make_dealer("D-003")})
        session_id = _selected_session(session_store)

        response = _service(llm, session_store, dealer_repo).execute(
            ChatRequest(session_id=session_id, message="dealer details")
        )

        assert response.reply == (
            "Prestige Cars (Bangalore)\n"
            "78 MG Road\n"
            "Phone: +91-80-2552-1003\n"
            "Email: sales@prestigecars.example\n"
            "Rating: 4.7/5"
        )

    def test_incomplete_dealer_row_shows_partial_details(
        self, session_store: SessionStore
    ) -> None:
        """Edge: missing email/rating → partial details, never a crash."""
        llm = FakeLLM()
        llm.enqueue(task_decision("DEALER_DETAILS"))
        llm.enqueue(ResponseWording(reply=""))
        dealer_repo = StubDealerRepository(
            by_id={"D-012": make_dealer("D-012", name="Apex AutoCare", email="", rating=None)}
        )
        session_id = _selected_session(session_store, car_id="C-0065", dealer_id="D-012")

        response = _service(llm, session_store, dealer_repo).execute(
            ChatRequest(session_id=session_id, message="dealer details")
        )

        assert response.reply.startswith("Apex AutoCare (Bangalore)")
        assert "Phone: +91-80-2552-1003" in response.reply
        assert "Rating:" not in response.reply
        assert response.workflow_state == "DEALER_DETAILS_SHOWN"

    def test_missing_dealer_row_reports_the_error(self, session_store: SessionStore) -> None:
        """Edge: a dealer id whose row is gone is a domain message, not a 500."""
        llm = FakeLLM()
        llm.enqueue(task_decision("DEALER_DETAILS"))
        dealer_repo = StubDealerRepository(by_id={})
        session_id = _selected_session(session_store, car_id="C-9004", dealer_id="D-999")

        response = _service(llm, session_store, dealer_repo).execute(
            ChatRequest(session_id=session_id, message="dealer details")
        )

        assert "Dealer not found: D-999" in response.reply
        assert response.workflow_state == "AWAITING_ACTION"

    def test_no_selected_dealer_asks_to_pick_a_car(self, session_store: SessionStore) -> None:
        """Guard branch: details before any car is selected."""
        llm = FakeLLM()
        llm.enqueue(task_decision("DEALER_DETAILS"))
        dealer_repo = StubDealerRepository(by_id={"D-003": make_dealer("D-003")})
        session_id = _selected_session(session_store, car_id=None, dealer_id=None)

        response = _service(llm, session_store, dealer_repo).execute(
            ChatRequest(session_id=session_id, message="dealer details")
        )

        assert response.reply == "No dealer selected. Please search for and select a car first."
        assert response.workflow_state == "AWAITING_ACTION"

    def test_another_dealer_request_stays_graceful(self, session_store: SessionStore) -> None:
        """Edge: 'another dealer' shows the current one again, no crash."""
        llm = FakeLLM()
        llm.enqueue(task_decision("DEALER_DETAILS"))
        llm.enqueue(wording_reply("Currently selected: Prestige Cars in Bangalore."))
        dealer_repo = StubDealerRepository(by_id={"D-003": make_dealer("D-003")})
        session_id = _selected_session(session_store, state="DEALER_DETAILS_SHOWN")

        response = _service(llm, session_store, dealer_repo).execute(
            ChatRequest(session_id=session_id, message="show me a different dealer")
        )

        assert response.reply == "Currently selected: Prestige Cars in Bangalore."
        assert response.workflow_state in {"DEALER_DETAILS_SHOWN", "AWAITING_ACTION"}
