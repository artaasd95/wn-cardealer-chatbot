"""Car table definition."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.tables.base import Base


class Car(Base):
    """Car inventory table."""

    __tablename__ = "car"

    car_id: Mapped[str] = mapped_column(String, primary_key=True)
    make: Mapped[str] = mapped_column(String, index=True)
    model: Mapped[str] = mapped_column(String, index=True)
    variant: Mapped[str | None] = mapped_column(String, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fuel_type: Mapped[str | None] = mapped_column(String, nullable=True)
    transmission: Mapped[str | None] = mapped_column(String, nullable=True)
    body_type: Mapped[str | None] = mapped_column(String, nullable=True)
    price_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mileage_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    features: Mapped[str | None] = mapped_column(String, nullable=True)
    dealer_id: Mapped[str] = mapped_column(String, ForeignKey("dealer.dealer_id"), index=True)

    def __repr__(self) -> str:
        """Return a readable representation."""
        return (
            f"Car(car_id={self.car_id}, make={self.make}, model={self.model}, "
            f"variant={self.variant}, dealer_id={self.dealer_id})"
        )
