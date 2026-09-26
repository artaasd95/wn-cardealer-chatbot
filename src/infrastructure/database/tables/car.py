"""Car table definition."""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Car(Base):
    """Car inventory table."""

    __tablename__ = "car"

    car_id = Column(String, primary_key=True)
    make = Column(String, nullable=False, index=True)
    model = Column(String, nullable=False, index=True)
    variant = Column(String, nullable=True)
    year = Column(Integer, nullable=True)
    fuel_type = Column(String, nullable=True)
    transmission = Column(String, nullable=True)
    body_type = Column(String, nullable=True)
    price_min = Column(Integer, nullable=True)
    price_max = Column(Integer, nullable=True)
    mileage_km = Column(Integer, nullable=True)
    features = Column(String, nullable=True)
    dealer_id = Column(String, ForeignKey("dealer.dealer_id"), nullable=False, index=True)

    def __repr__(self) -> str:
        """Return a readable representation."""
        return (
            f"Car(car_id={self.car_id}, make={self.make}, model={self.model}, "
            f"variant={self.variant}, dealer_id={self.dealer_id})"
        )
