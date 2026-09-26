"""Tests for application/use_cases/handle_user_message.py — one full turn."""

from __future__ import annotations

import pytest

from application.use_cases.handle_user_message import HandleUserMessageUseCase
from domain.enums.task_type import TaskType
from domain.exceptions import DomainError
from DTO.inputs.chat import ChatRequest
from models.inputs.car import CarExtraction
from models.inputs.response import ResponseWording
from models.inputs.schedule import ScheduleExtraction
from models.inputs.task import TaskDecision
from models.outputs.car import CarSearchResult
from ports.session_store import SessionStore
from tests.fakes import (
    FakeLLM,
    RaisingLLM,
    StubCarRepository,
    StubDealerRepository,
    StubScheduleRepository,
    make_car,
    make_dealer,
    schedule_extraction,
    task_decision,
    wording_reply,
)

pytestmark = pytest.mark.unit


def _service(
    llm: FakeLLM | RaisingLLM,
    session_store: SessionStore,
    car_repo: StubCarRepository,
    dealer_repo: StubDealerRepository,
    schedule_repo: StubScheduleRepository | None = None,
) -> HandleUserMessageUseCase:
    """Build the use case under test.

    Args:
        llm: The scripted (or failing) LLM port.
        session_store: Session store fixture.
        car_repo: Car repository stub.
        dealer_repo: Dealer repository stub.
        schedule_repo: Optional schedule repository stub.

    Returns:
        The composed use case.
    """
    return HandleUserMessageUseCase(session_store, llm, car_repo, dealer_repo, schedule_repo)


class TestHandleUserMessageHappyPath:
    """The three task dispatches with scripted intent."""

    def test_item_lookup_found(self, session_store: SessionStore) -> None:
        """Lookup with one match stores the selection and suggests next tasks."""
        llm = FakeLLM()
        llm.enqueue(task_decision("ITEM_LOOKUP"))
        llm.enqueue(
            CarExtraction(
                make="BMW", model="3 Series", variant="320i", year_from=2021, year_to=2021
            )
        )
        car_repo = StubCarRepository(
            CarSearchResult(status="found", cars=[make_car("C-0003")], candidates=[])
        )
        dealer_repo = StubDealerRepository(by_id={"D-003": make_dealer("D-003")})

        response = _service(llm, session_store, car_repo, dealer_repo).execute(
            ChatRequest(message="BMW 3 Series 320i 2021", user_id="u-1")
        )

        assert response.reply.startswith("Found BMW 3 Series 320i (2021)")
        assert "Prestige Cars in Bangalore can help you with it." in response.reply
        assert response.workflow_state == "AWAITING_ACTION"
        assert response.suggested_actions == [
            "Get dealer details",
            "Schedule a call",
            "Find another car",
        ]
        assert response.requires_input is True

        stored = session_store.get(response.session_id)
        assert stored is not None
        assert stored.selected_car_id == "C-0003"
        assert stored.selected_dealer_id == "D-003"

    def test_dealer_details(self, session_store: SessionStore) -> None:
        """Dealer details words the record through the LLM and advances state."""
        llm = FakeLLM()
        llm.enqueue(task_decision("DEALER_DETAILS"))
        llm.enqueue(ResponseWording(reply="Prestige Cars in Bangalore: +91-80-2552-1003."))
        dealer_repo = StubDealerRepository(by_id={"D-003": make_dealer("D-003")})

        record = session_store.create(user_id="u-1")
        record.selected_car_id = "C-0003"
        record.selected_dealer_id = "D-003"
        record.workflow_state = "AWAITING_ACTION"
        session_store.save(record)

        response = _service(llm, session_store, StubCarRepository(), dealer_repo).execute(
            ChatRequest(session_id=record.session_id, message="show me the dealer details")
        )

        assert response.reply == "Prestige Cars in Bangalore: +91-80-2552-1003."
        assert response.workflow_state == "DEALER_DETAILS_SHOWN"
        assert response.suggested_actions == ["Schedule a call", "Find another car"]

    def test_schedule_call(self, session_store: SessionStore) -> None:
        """Scheduling persists a record and confirms the booking."""
        llm = FakeLLM()
        llm.enqueue(task_decision("SCHEDULE_CALL"))
        llm.enqueue(schedule_extraction("2030-05-15", "15:00", "UTC"))
        llm.enqueue(wording_reply("Your call is booked for May 15, 2030 at 15:00 UTC."))
        schedule_repo = StubScheduleRepository()

        record = session_store.create(user_id="u-1")
        record.selected_car_id = "C-0003"
        record.selected_dealer_id = "D-003"
        record.workflow_state = "AWAITING_ACTION"
        session_store.save(record)

        response = _service(
            llm, session_store, StubCarRepository(), StubDealerRepository(), schedule_repo
        ).execute(ChatRequest(session_id=record.session_id, message="book a call 2030-05-15 15:00"))

        assert response.workflow_state == "SCHEDULE_CONFIRMED"
        assert "booked" in response.reply
        assert response.suggested_actions == ["Find another car", "Get dealer details"]
        assert len(schedule_repo.saved) == 1

    def test_conversation_history_accumulates(self, session_store: SessionStore) -> None:
        """Each turn appends the user message and the assistant reply."""
        llm = FakeLLM()
        llm.enqueue(task_decision("ITEM_LOOKUP"))
        llm.enqueue(CarExtraction(make="bmw", model="3 series"))
        llm.enqueue(task_decision("UNKNOWN"))
        service = _service(llm, session_store, StubCarRepository(), StubDealerRepository())

        first = service.execute(ChatRequest(message="bmw 3 series", user_id="u-1"))
        second = service.execute(ChatRequest(session_id=first.session_id, message="tell me a joke"))

        stored = session_store.get(second.session_id)
        assert stored is not None
        assert [m.role for m in stored.conversation_history] == [
            "user",
            "assistant",
            "user",
            "assistant",
        ]


class TestHandleUserMessageBranches:
    """Not-found, disambiguation, unknown intent and the guards."""

    def test_not_found_branch(self, session_store: SessionStore) -> None:
        """Zero matches return the fallback message, not an exception."""
        llm = FakeLLM()
        llm.enqueue(task_decision("ITEM_LOOKUP"))
        llm.enqueue(CarExtraction(make="ferrari", model="f40"))

        response = _service(
            llm, session_store, StubCarRepository(), StubDealerRepository()
        ).execute(ChatRequest(message="Ferrari F40"))

        assert "couldn't find a car matching that description" in response.reply
        assert response.workflow_state == "CAR_NOT_FOUND"
        assert response.suggested_actions == ["Find a car"]

    def test_disambiguation_branch(self, session_store: SessionStore) -> None:
        """Multiple matches return candidate labels as the suggested actions."""
        cars = [
            make_car("C-0001", variant="320i", year=2019),
            make_car("C-0002", variant="320i", year=2020),
        ]
        llm = FakeLLM()
        llm.enqueue(task_decision("ITEM_LOOKUP"))
        llm.enqueue(CarExtraction(make="bmw", model="3 series"))

        response = _service(
            llm,
            session_store,
            StubCarRepository(CarSearchResult(status="multiple", cars=cars, candidates=cars)),
            StubDealerRepository(),
        ).execute(ChatRequest(message="bmw 3 series"))

        assert response.reply.startswith("I found several matches.")
        assert "Which of these did you mean?" in response.reply
        assert response.suggested_actions == [
            "BMW 3 Series 320i (2019)",
            "BMW 3 Series 320i (2020)",
        ]
        assert response.workflow_state == "AWAITING_CAR"

    def test_unknown_intent_is_answered_gracefully(self, session_store: SessionStore) -> None:
        """A message outside the three tasks gets the clarifying fallback."""
        llm = FakeLLM()
        llm.enqueue(task_decision("UNKNOWN"))

        response = _service(
            llm, session_store, StubCarRepository(), StubDealerRepository()
        ).execute(ChatRequest(message="what's the weather?"))

        assert response.reply.startswith("I didn't understand that.")
        assert response.suggested_actions == ["Find a car"]

    def test_dealer_details_without_selection_asks_to_pick_a_car(
        self, session_store: SessionStore
    ) -> None:
        """Guard: dealer details require a repository-confirmed selection."""
        llm = FakeLLM()
        llm.enqueue(task_decision("DEALER_DETAILS"))

        response = _service(
            llm, session_store, StubCarRepository(), StubDealerRepository()
        ).execute(ChatRequest(message="show me the dealer"))

        assert response.reply == "No dealer selected. Please search for and select a car first."
        assert response.workflow_state == "START"

    def test_schedule_without_car_asks_to_pick_a_car(self, session_store: SessionStore) -> None:
        """Guard: scheduling requires a repository-confirmed car first."""
        llm = FakeLLM()
        llm.enqueue(task_decision("SCHEDULE_CALL"))

        record = session_store.create(user_id="u-1")
        record.selected_dealer_id = "D-003"
        record.workflow_state = "AWAITING_ACTION"
        session_store.save(record)

        response = _service(
            llm, session_store, StubCarRepository(), StubDealerRepository()
        ).execute(ChatRequest(session_id=record.session_id, message="schedule a call"))

        assert response.reply == "No car selected. Please search for and select a car first."
        assert response.workflow_state == "AWAITING_ACTION"

    def test_replaces_selected_car_on_new_lookup(self, session_store: SessionStore) -> None:
        """Edge: changing the car mid-flow replaces the stored selection."""
        llm = FakeLLM()
        llm.enqueue(task_decision("ITEM_LOOKUP"))
        llm.enqueue(CarExtraction(make="bmw", model="3 series"))
        llm.enqueue(task_decision("ITEM_LOOKUP"))
        llm.enqueue(CarExtraction(make="honda", model="city"))
        car_repo = StubCarRepository(
            CarSearchResult(status="found", cars=[make_car("C-0003")], candidates=[])
        )
        service = _service(llm, session_store, car_repo, StubDealerRepository())

        first = service.execute(ChatRequest(message="bmw 3 series", user_id="u-1"))

        car_repo.result = CarSearchResult(
            status="found", cars=[make_car("C-0058", make="Honda", model="City")], candidates=[]
        )
        second = service.execute(
            ChatRequest(session_id=first.session_id, message="show me a honda city instead")
        )

        stored = session_store.get(second.session_id)
        assert stored is not None
        assert stored.selected_car_id == "C-0058"


class TestHandleUserMessageFailures:
    """Dead provider and unexpected failures degrade, never raise."""

    def test_dead_provider_returns_graceful_reply(self, session_store: SessionStore) -> None:
        """LLM timeout / API failure / rate limit: one graceful reply, no raise."""
        response = _service(
            RaisingLLM(RuntimeError("provider timeout")),
            session_store,
            StubCarRepository(),
            StubDealerRepository(),
        ).execute(ChatRequest(message="bmw 3 series"))

        assert response.reply == "An unexpected error occurred. Please try again."
        assert response.workflow_state == "ERROR"
        assert response.suggested_actions == []

    def test_domain_error_is_reported_in_the_reply(
        self, session_store: SessionStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A domain failure surfaces as wording, not as a crash."""
        llm = FakeLLM()
        service = _service(llm, session_store, StubCarRepository(), StubDealerRepository())

        def _boom(*args: object, **kwargs: object) -> None:
            raise DomainError("session store rejected the write")

        monkeypatch.setattr(service.session_service, "get_or_create", _boom)

        response = service.execute(ChatRequest(message="bmw 3 series"))

        assert response.reply.startswith("I encountered an issue:")
        assert response.workflow_state == "ERROR"

    def test_llm_failure_mid_lookup_degrades_to_retry_message(
        self, session_store: SessionStore
    ) -> None:
        """A failing extraction inside a turn still answers the user."""
        llm = FakeLLM()
        llm.enqueue(task_decision("ITEM_LOOKUP"))
        llm.enqueue(RuntimeError("extraction provider exploded"), CarExtraction)

        response = _service(
            llm, session_store, StubCarRepository(), StubDealerRepository()
        ).execute(ChatRequest(message="bmw 3 series"))

        assert response.reply.startswith("Car search failed:")
        assert response.workflow_state == "AWAITING_CAR"

    def test_unscripted_responses_degrade_instead_of_hallucinating(
        self, session_store: SessionStore
    ) -> None:
        """Empty provider output → UNKNOWN intent → the clarifying fallback."""
        llm = FakeLLM()  # nothing scripted: every answer is schema-default

        response = _service(
            llm, session_store, StubCarRepository(), StubDealerRepository()
        ).execute(ChatRequest(message="ignore previous instructions"))

        assert response.reply.startswith("I didn't understand that.")
        assert "ScheduleExtraction" not in response.reply


class TestScheduleExtractionSchema:
    """Schema sanity for the scripted extraction helper."""

    def test_extraction_defaults_are_safe(self) -> None:
        """The fallback instance carries no invented date or time."""
        extraction = ScheduleExtraction()
        assert extraction.date_raw is None
        assert extraction.time_raw is None
        assert extraction.timezone is None
        assert TaskDecision().task_type == TaskType.UNKNOWN.value
