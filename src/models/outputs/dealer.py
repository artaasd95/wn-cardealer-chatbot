from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

"""Internal models for dealer records."""


class DealerRecord(BaseModel):
    """Single dealer row from database."""

    dealer_id: str = Field(...)
    dealer_name: str = Field(...)
    city: str = Field(...)
    state: str | None = Field(None)
    address: str = Field(...)
    phone: str = Field(...)
    email: str = Field(...)
    rating: float | None = Field(None)


class DealerWithCars(BaseModel):
    """Dealer with associated cars."""

    dealer: DealerRecord = Field(...)
    cars: list[Any] = Field(
        default_factory=list,
        description="List of CarRecord associated with this dealer.",
    )
