"""Dealer repository implementation."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from infrastructure.database.tables.car import Car
from infrastructure.database.tables.dealer import Dealer
from models.outputs.dealer import DealerRecord, DealerWithCars
from ports.repositories.dealer_repository import DealerRepository

logger = logging.getLogger(__name__)


class DealerRepositoryImpl(DealerRepository):
    """SQLAlchemy-based dealer repository."""

    def __init__(self, session: Session) -> None:
        """Initialize with a database session.

        Args:
            session: SQLAlchemy Session instance.
        """
        self.session = session

    def get_by_id(self, dealer_id: str) -> DealerRecord | None:
        """Retrieve a dealer by ID.

        Args:
            dealer_id: The dealer identifier.

        Returns:
            DealerRecord if found, None otherwise.
        """
        dealer = self.session.query(Dealer).filter(Dealer.dealer_id == dealer_id).first()
        return self._dealer_record(dealer) if dealer else None

    def get_with_cars(self, dealer_id: str) -> DealerWithCars | None:
        """Retrieve a dealer and all their cars.

        Args:
            dealer_id: The dealer identifier.

        Returns:
            DealerWithCars with dealer details and car list, or None if dealer not found.
        """
        dealer = self.session.query(Dealer).filter(Dealer.dealer_id == dealer_id).first()
        if not dealer:
            return None

        cars = self.session.query(Car).filter(Car.dealer_id == dealer_id).all()

        return DealerWithCars(
            dealer=self._dealer_record(dealer),
            cars=[
                {
                    "car_id": car.car_id,
                    "make": car.make,
                    "model": car.model,
                    "variant": car.variant,
                    "year": car.year,
                    "price_min": car.price_min,
                    "price_max": car.price_max,
                }
                for car in cars
            ],
        )

    def search_by_city(self, city: str) -> list[DealerRecord]:
        """Search for dealers in a city.

        Args:
            city: The city name to search for.

        Returns:
            List of matching DealerRecords, or empty list.
        """
        dealers = self.session.query(Dealer).filter(Dealer.city.ilike(f"%{city}%")).all()
        return [self._dealer_record(d) for d in dealers]

    @staticmethod
    def _dealer_record(dealer: Dealer) -> DealerRecord:
        """Convert a Dealer ORM object to a DealerRecord DTO.

        Args:
            dealer: SQLAlchemy Dealer instance.

        Returns:
            DealerRecord DTO.
        """
        return DealerRecord(
            dealer_id=dealer.dealer_id,
            dealer_name=dealer.dealer_name,
            city=dealer.city,
            state=dealer.state,
            address=dealer.address,
            phone=dealer.phone,
            email=dealer.email,
            rating=dealer.rating,
        )
