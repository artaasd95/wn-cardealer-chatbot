"""Item lookup flow branches (plan Phase 8: one test per flow branch)."""

from __future__ import annotations

import pytest

from application.tasks.item_lookup.workflow import ItemLookupWorkflow
from application.use_cases.handle_user_message import HandleUserMessageUseCase
from domain.enums.workflow_state import WorkflowState
from DTO.inputs.chat import ChatRequest
from DTO.outputs.chat import ChatResponse
from models.inputs.car import CarExtraction
from models.outputs.car import CarSearchResult
from ports.session_store import SessionStore
from tests.fakes import (
    FakeLLM,
    StubCarRepository,
    StubDealerRepository,
    make_car,
    make_dealer,
    task_decision,
)

pytestmark = pytest.mark.unit


def _service(
    llm: FakeLLM,
    session_store: SessionStore,
    car_repo: StubCarRepository,
    dealer_repo: StubDealerRepository | None = None,
) -> HandleUserMessageUseCase:
    """Compose the turn handler under test.

    Args:
        llm: Scripted LLM port.
        session_store: Session store fixture.
        car_repo: Car repository stub.
        dealer_repo: Optional dealer repository stub.

    Returns:
        The turn handler.
    """
    return HandleUserMessageUseCase(
        session_store, llm, car_repo, dealer_repo or StubDealerRepository()
    )


def _lookup_turn(
    service: HandleUserMessageUseCase,
    message: str = "bmw 3 series 320i 2021",
    session_id: str | None = None,
) -> ChatResponse:
    """Run one lookup turn.

    Args:
        service: The turn handler.
        message: The user message.
        session_id: Optional session to continue.

    Returns:
        The ChatResponse.
    """
    return service.execute(ChatRequest(session_id=session_id, message=message))


class TestItemLookupWorkflowStates:
    """ItemLookupWorkflow.advance: one assertion per result status."""

    def test_found_with_dealer_advances_to_awaiting_action(self) -> None:
        """Found + dealer confirmed → the user may act immediately."""
        result = CarSearchResult(status="found", cars=[make_car()], candidates=[])
        assert ItemLookupWorkflow.advance(result, dealer_found=True) is (
            WorkflowState.AWAITING_ACTION
        )

    def test_found_without_dealer_advances_to_car_selected(self) -> None:
        """Found + no dealer → CAR_SELECTED, dealer work still pending."""
        result = CarSearchResult(status="found", cars=[make_car()], candidates=[])
        assert ItemLookupWorkflow.advance(result, dealer_found=False) is (
            WorkflowState.CAR_SELECTED
        )

    def test_multiple_stays_awaiting_car(self) -> None:
        """Multiple matches wait for the user's pick."""
        result = CarSearchResult(status="multiple", cars=[make_car()], candidates=[])
        assert ItemLookupWorkflow.advance(result) is WorkflowState.AWAITING_CAR

    def test_not_found_advances_to_car_not_found(self) -> None:
        """Zero matches land on CAR_NOT_FOUND and can retry."""
        result = CarSearchResult(status="not_found", cars=[], candidates=[])
        assert ItemLookupWorkflow.advance(result) is WorkflowState.CAR_NOT_FOUND


class TestItemLookupBranches:
    """The user-visible branches of the item lookup flow."""

    def test_zero_results_returns_fallback_message(self, session_store: SessionStore) -> None:
        """0 results → fallback message, no exception, CAR_NOT_FOUND."""
        llm = FakeLLM()
        llm.enqueue(task_decision("ITEM_LOOKUP"))
        llm.enqueue(CarExtraction(make="ferrari", model="f40"))
        car_repo = StubCarRepository(CarSearchResult(status="not_found"))

        response = _lookup_turn(_service(llm, session_store, car_repo), "Ferrari F40")

        assert "couldn't find a car matching that description" in response.reply
        assert response.workflow_state == "CAR_NOT_FOUND"

    def test_multiple_results_return_candidate_list(self, session_store: SessionStore) -> None:
        """Branch: >1 results → disambiguation carrying the candidate labels."""
        cars = [
            make_car("C-0001", variant="320i", year=2019),
            make_car("C-0002", variant="320i", year=2020),
            make_car("C-0004", variant="330i", year=2019),
        ]
        llm = FakeLLM()
        llm.enqueue(task_decision("ITEM_LOOKUP"))
        llm.enqueue(CarExtraction(make="bmw", model="3 series"))
        car_repo = StubCarRepository(
            CarSearchResult(status="multiple", cars=cars, candidates=cars[:5])
        )

        response = _lookup_turn(_service(llm, session_store, car_repo), "bmw 3 series")

        assert "I found several matches." in response.reply
        assert "Pick one:" in response.reply
        assert response.suggested_actions == [
            "BMW 3 Series 320i (2019)",
            "BMW 3 Series 320i (2020)",
            "BMW 3 Series 330i (2019)",
        ]
        assert response.workflow_state == "AWAITING_CAR"

    def test_single_result_presents_car_and_dealer(self, session_store: SessionStore) -> None:
        """Branch: exactly one result presents the car, price and dealer."""
        llm = FakeLLM()
        llm.enqueue(task_decision("ITEM_LOOKUP"))
        llm.enqueue(CarExtraction(make="bmw", model="3 series", variant="320i", year_from=2021))
        car_repo = StubCarRepository(
            CarSearchResult(status="found", cars=[make_car("C-0003")], candidates=[])
        )
        dealer_repo = StubDealerRepository(by_id={"D-003": make_dealer("D-003")})

        response = _lookup_turn(_service(llm, session_store, car_repo, dealer_repo))

        assert response.reply == (
            "Found BMW 3 Series 320i (2021) — $3,500,000 - $4,100,000. "
            "Prestige Cars in Bangalore can help you with it. "
            "Would you like dealer details or to schedule a call?"
        )
        assert response.workflow_state == "AWAITING_ACTION"

    def test_car_without_dealer_still_selects_the_car(self, session_store: SessionStore) -> None:
        """Edge: car exists but its dealer does not → CAR_SELECTED, no crash."""
        car = make_car(
            "C-9004",
            make="Tata",
            model="Punch",
            variant="Creative S",
            year=2024,
            dealer_id="D-999",
        )
        llm = FakeLLM()
        llm.enqueue(task_decision("ITEM_LOOKUP"))
        llm.enqueue(CarExtraction(make="tata", model="punch", variant="creative s"))
        car_repo = StubCarRepository(CarSearchResult(status="found", cars=[car], candidates=[]))

        response = _lookup_turn(
            _service(llm, session_store, car_repo), "Tata Punch Creative S 2024"
        )

        assert response.reply.startswith("Found Tata Punch Creative S (2024)")
        assert "can help you with it" not in response.reply
        assert response.workflow_state == "CAR_SELECTED"

    def test_missing_prices_render_as_ask_the_dealer(self, session_store: SessionStore) -> None:
        """Edge: invalid/incomplete car data renders placeholders, not errors."""
        car = make_car(
            "C-9002",
            make="Nissan",
            model="Kicks",
            variant=None,
            year=2023,
            dealer_id="D-010",
            price_min=None,
            price_max=None,
        )
        llm = FakeLLM()
        llm.enqueue(task_decision("ITEM_LOOKUP"))
        llm.enqueue(CarExtraction(make="nissan", model="kicks", year_from=2023, year_to=2023))
        car_repo = StubCarRepository(CarSearchResult(status="found", cars=[car], candidates=[]))

        response = _lookup_turn(_service(llm, session_store, car_repo), "Nissan Kicks 2023")

        assert response.reply.startswith("Found Nissan Kicks (2023) — Ask the dealer.")
        # no dealer stub wired here: the missing dealer is its own branch
        assert response.workflow_state == "CAR_SELECTED"

    def test_extraction_is_normalized_before_search(self, session_store: SessionStore) -> None:
        """Capitalization/alias input is normalized before it reaches SQL."""
        llm = FakeLLM()
        llm.enqueue(task_decision("ITEM_LOOKUP"))
        llm.enqueue(CarExtraction(make=" B.M.W. ", model=" 3 Series ", variant=" 320i "))
        car_repo = StubCarRepository(CarSearchResult(status="not_found"))

        _lookup_turn(_service(llm, session_store, car_repo), "B.M.W. 3 Series 320i")

        query = car_repo.queries[0]
        assert (query.make, query.model, query.variant) == ("b.m.w.", "3 series", "320i")


class TestItemLookupGuards:
    """Downstream tasks refuse to run without a repository-confirmed car."""

    def test_dealer_details_requires_a_selected_car(self, session_store: SessionStore) -> None:
        """Guard branch: dealer details before any car is selected."""
        llm = FakeLLM()
        llm.enqueue(task_decision("DEALER_DETAILS"))

        response = _service(llm, session_store, StubCarRepository()).execute(
            ChatRequest(message="dealer details please")
        )

        assert response.reply == "No dealer selected. Please search for and select a car first."

    def test_schedule_call_requires_a_selected_car(self, session_store: SessionStore) -> None:
        """Guard branch: scheduling before any car is selected."""
        llm = FakeLLM()
        llm.enqueue(task_decision("SCHEDULE_CALL"))

        response = _service(llm, session_store, StubCarRepository()).execute(
            ChatRequest(message="schedule a call")
        )

        assert response.reply == "No dealer selected. Please search for and select a car first."
