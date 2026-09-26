"""Tests for application/use_cases/lookup_car.py."""

from __future__ import annotations

import pytest

from application.use_cases.lookup_car import LookupCarUseCase
from domain.enums.workflow_state import WorkflowState
from models.inputs.car import CarExtraction
from models.outputs.car import CarSearchResult
from tests.fakes import (
    FakeLLM,
    StubCarRepository,
    StubDealerRepository,
    make_car,
    make_dealer,
)

pytestmark = pytest.mark.unit


class TestLookupCarUseCase:
    """Steps 1-5 of the item lookup flow: extract, normalize, search, dealer."""

    def test_found_with_dealer(
        self, fake_llm: FakeLLM, stub_car_repo: StubCarRepository
    ) -> None:
        """Happy path: one match loads its dealer and can act immediately."""
        car = make_car("C-0003", dealer_id="D-003")
        dealer = make_dealer("D-003")
        stub_car_repo.result = CarSearchResult(status="found", cars=[car], candidates=[])
        stub_dealer_repo = StubDealerRepository(by_id={"D-003": dealer})
        fake_llm.enqueue(
            CarExtraction(
                make=" BMW ", model=" 3 Series ", variant="320i", year_from=2021, year_to=2021
            )
        )

        result, loaded_dealer, next_state = LookupCarUseCase(
            fake_llm, stub_car_repo, stub_dealer_repo
        ).execute("I want a BMW 3 Series 320i 2021")

        assert result.status == "found"
        assert loaded_dealer == dealer
        assert next_state is WorkflowState.AWAITING_ACTION
        # Step 2: normalization happened before the query reached the repository
        query = stub_car_repo.queries[0]
        assert (query.make, query.model, query.variant) == ("bmw", "3 series", "320i")
        assert (query.year_from, query.year_to) == (2021, 2021)
        # Step 4: the dealer was loaded for the matched car
        assert stub_dealer_repo.requested == ["D-003"]

    def test_found_but_dealer_missing(
        self, fake_llm: FakeLLM, stub_car_repo: StubCarRepository
    ) -> None:
        """Edge case: a car whose dealer row is gone still selects the car."""
        car = make_car("C-9004", make="Tata", model="Punch", dealer_id="D-999")
        stub_car_repo.result = CarSearchResult(status="found", cars=[car], candidates=[])
        stub_dealer_repo = StubDealerRepository(by_id={})
        fake_llm.enqueue(CarExtraction(make="tata", model="punch", variant="creative s"))

        result, loaded_dealer, next_state = LookupCarUseCase(
            fake_llm, stub_car_repo, stub_dealer_repo
        ).execute("Tata Punch Creative S")

        assert result.status == "found"
        assert loaded_dealer is None
        assert next_state is WorkflowState.CAR_SELECTED

    def test_dealer_repository_failure_is_not_fatal(
        self, fake_llm: FakeLLM, stub_car_repo: StubCarRepository
    ) -> None:
        """Failure branch: a dealer query failure keeps the car, drops the dealer."""
        car = make_car("C-0003")
        stub_car_repo.result = CarSearchResult(status="found", cars=[car], candidates=[])
        stub_dealer_repo = StubDealerRepository(error=RuntimeError("db down"))
        fake_llm.enqueue(CarExtraction(make="bmw", model="3 series"))

        result, loaded_dealer, next_state = LookupCarUseCase(
            fake_llm, stub_car_repo, stub_dealer_repo
        ).execute("bmw 3 series")

        assert result.status == "found"
        assert loaded_dealer is None
        assert next_state is WorkflowState.CAR_SELECTED

    def test_multiple_matches_stay_awaiting_car(
        self, fake_llm: FakeLLM, stub_car_repo: StubCarRepository
    ) -> None:
        """Branch: more than one match waits for the user to disambiguate."""
        cars = [
            make_car("C-0001", variant="320i", year=2019),
            make_car("C-0002", variant="320i", year=2020),
        ]
        stub_car_repo.result = CarSearchResult(status="multiple", cars=cars, candidates=cars)
        fake_llm.enqueue(CarExtraction(make="bmw", model="3 series"))

        result, loaded_dealer, next_state = LookupCarUseCase(
            fake_llm, stub_car_repo, StubDealerRepository()
        ).execute("bmw 3 series")

        assert result.status == "multiple"
        assert loaded_dealer is None
        assert next_state is WorkflowState.AWAITING_CAR

    def test_not_found_is_a_branch_not_an_exception(
        self, fake_llm: FakeLLM, stub_car_repo: StubCarRepository
    ) -> None:
        """Branch: zero matches return a result object, never a raise."""
        stub_car_repo.result = CarSearchResult(status="not_found", cars=[], candidates=[])
        fake_llm.enqueue(CarExtraction(make="ferrari", model="f40"))

        result, loaded_dealer, next_state = LookupCarUseCase(
            fake_llm, stub_car_repo, StubDealerRepository()
        ).execute("Ferrari F40")

        assert result.status == "not_found"
        assert result.cars == []
        assert loaded_dealer is None
        assert next_state is WorkflowState.CAR_NOT_FOUND

    def test_search_failure_propagates_to_the_turn_handler(
        self, fake_llm: FakeLLM, stub_car_repo: StubCarRepository
    ) -> None:
        """Failure branch: a query failure surfaces for the turn handler to degrade."""
        stub_car_repo.error = RuntimeError("query failed")
        fake_llm.enqueue(CarExtraction(make="bmw"))

        with pytest.raises(RuntimeError, match="query failed"):
            LookupCarUseCase(fake_llm, stub_car_repo, StubDealerRepository()).execute("bmw")
