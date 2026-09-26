"""Car repository implementation."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from infrastructure.database.tables.car import Car
from models.inputs.car import NormalizedCarQuery
from models.outputs.car import CarRecord, CarSearchResult
from ports.repositories.car_repository import CarRepository

logger = logging.getLogger(__name__)


class CarRepositoryImpl(CarRepository):
    """SQLAlchemy-based car repository."""

    def __init__(self, session: Session) -> None:
        """Initialize with a database session.

        Args:
            session: SQLAlchemy Session instance.
        """
        self.session = session

    def search(self, query: NormalizedCarQuery) -> CarSearchResult:
        """Search for cars matching the normalized query.

        Args:
            query: Normalized car search query.

        Returns:
            CarSearchResult with status and matching cars.
        """
        q = self.session.query(Car)

        if query.make:
            q = q.filter(Car.make.ilike(f"%{query.make}%"))

        if query.model:
            q = q.filter(Car.model.ilike(f"%{query.model}%"))

        if query.variant:
            q = q.filter(Car.variant.ilike(f"%{query.variant}%"))

        if query.year_from is not None:
            q = q.filter(Car.year >= query.year_from)

        if query.year_to is not None:
            q = q.filter(Car.year <= query.year_to)

        cars = q.all()

        if len(cars) == 0:
            return CarSearchResult(status="not_found", cars=[], candidates=[])

        if len(cars) == 1:
            car = cars[0]
            return CarSearchResult(
                status="found",
                cars=[self._car_record(car)],
                candidates=[],
            )

        # Multiple matches: return all cars and a reduced candidate list
        records = [self._car_record(car) for car in cars]
        candidates = records[:5]  # Show up to 5 for disambiguation

        return CarSearchResult(
            status="multiple",
            cars=records,
            candidates=candidates,
        )

    def get_by_id(self, car_id: str) -> CarRecord | None:
        """Retrieve a car by ID.

        Args:
            car_id: The car identifier.

        Returns:
            CarRecord if found, None otherwise.
        """
        car = self.session.query(Car).filter(Car.car_id == car_id).first()
        return self._car_record(car) if car else None

    def search_by_alias(self, alias: str) -> list[str]:
        """Look up normalized forms of an alias.

        Args:
            alias: An alias (make, model, or variant).

        Returns:
            List of normalized forms matching the alias, or empty list.
        """
        # This would typically query an aliases table or mapping.
        # For now, return empty to avoid extra I/O.
        return []

    @staticmethod
    def _car_record(car: Car) -> CarRecord:
        """Convert a Car ORM object to a CarRecord DTO.

        Args:
            car: SQLAlchemy Car instance.

        Returns:
            CarRecord DTO.
        """
        return CarRecord(
            car_id=car.car_id,
            make=car.make,
            model=car.model,
            variant=car.variant,
            year=car.year,
            fuel_type=car.fuel_type,
            transmission=car.transmission,
            body_type=car.body_type,
            price_min=car.price_min,
            price_max=car.price_max,
            mileage_km=car.mileage_km,
            features=car.features,
            dealer_id=car.dealer_id,
        )
