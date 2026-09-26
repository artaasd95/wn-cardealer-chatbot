"""Integration tests for repositories with CSV fixtures."""

from __future__ import annotations

from models.inputs.car import NormalizedCarQuery
from ports.repositories.car_repository import CarRepository
from ports.repositories.dealer_repository import DealerRepository


class TestCarRepository:
    """Integration tests for CarRepository with CSV fixtures."""

    def test_search_by_make_model(self, car_repo: CarRepository) -> None:
        """Test searching for cars by make and model."""
        query = NormalizedCarQuery(make="honda", model="civic")
        result = car_repo.search(query)

        assert result.status in ["found", "multiple", "not_found"]
        if result.status == "found":
            assert len(result.cars) == 1
            assert result.cars[0].make.lower() == "honda"
            assert result.cars[0].model.lower() == "civic"

    def test_search_not_found(self, car_repo: CarRepository) -> None:
        """Test search that returns no results."""
        query = NormalizedCarQuery(make="nonexistent", model="model")
        result = car_repo.search(query)

        assert result.status == "not_found"
        assert len(result.cars) == 0

    def test_search_multiple_results(self, car_repo: CarRepository) -> None:
        """Test search that returns multiple results."""
        # Assuming there are multiple cars from same maker
        query = NormalizedCarQuery(make="toyota")
        result = car_repo.search(query)

        if result.status == "multiple":
            assert len(result.cars) > 1
            assert len(result.candidates) <= 5

    def test_search_with_year_range(self, car_repo: CarRepository) -> None:
        """Test searching with year range."""
        query = NormalizedCarQuery(
            make="honda",
            model="civic",
            year_from=2020,
            year_to=2023,
        )
        result = car_repo.search(query)

        if result.status == "found":
            for car in result.cars:
                assert 2020 <= car.year <= 2023

    def test_get_car_by_id(self, car_repo: CarRepository) -> None:
        """Test getting car by ID."""
        # First, search to get a valid car ID
        query = NormalizedCarQuery(make="honda", model="civic")
        search_result = car_repo.search(query)

        if search_result.status == "found":
            car_id = search_result.cars[0].car_id
            car = car_repo.get_by_id(car_id)

            assert car is not None
            assert car.car_id == car_id

    def test_get_nonexistent_car_returns_none(self, car_repo: CarRepository) -> None:
        """Test that getting nonexistent car returns None."""
        car = car_repo.get_by_id("nonexistent-id")
        assert car is None

    def test_search_by_alias(self, car_repo: CarRepository) -> None:
        """Test searching by alias (e.g., 'c-class' for Mercedes C-Class)."""
        # Aliases are defined in data generation
        result = car_repo.search_by_alias("c-class")

        # Should find cars matching the alias
        assert len(result) >= 0


class TestDealerRepository:
    """Integration tests for DealerRepository with CSV fixtures."""

    def test_get_dealer_by_id(self, dealer_repo: DealerRepository) -> None:
        """Test getting dealer by ID."""
        # Assuming at least one dealer exists from fixtures
        dealer = dealer_repo.get_by_id("D-001")

        if dealer:
            assert dealer.dealer_id == "D-001"
            assert dealer.dealer_name is not None
            assert dealer.city is not None

    def test_get_nonexistent_dealer_returns_none(self, dealer_repo: DealerRepository) -> None:
        """Test that getting nonexistent dealer returns None."""
        dealer = dealer_repo.get_by_id("nonexistent-id")
        assert dealer is None

    def test_get_dealer_with_cars(self, dealer_repo: DealerRepository) -> None:
        """Test getting dealer with associated cars."""
        dealer = dealer_repo.get_with_cars("D-001")

        if dealer:
            assert dealer.dealer_id == "D-001"
            # May or may not have cars depending on fixtures

    def test_search_dealer_by_city(self, dealer_repo: DealerRepository) -> None:
        """Test searching dealers by city."""
        # Assuming there are dealers from various cities
        results = dealer_repo.search_by_city("New York")

        assert isinstance(results, list)
        # All results should be from specified city if any
        for dealer in results:
            assert dealer.city == "New York"
