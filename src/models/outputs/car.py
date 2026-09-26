from __future__ import annotations

from pydantic import BaseModel, Field

"""Internal models for car records and search results."""


class CarRecord(BaseModel):
    """Single car row from database."""

    car_id: str = Field(...)
    make: str = Field(...)
    model: str = Field(...)
    variant: str | None = Field(None)
    year: int = Field(...)
    fuel_type: str | None = Field(None)
    transmission: str | None = Field(None)
    body_type: str | None = Field(None)
    price_min: float | None = Field(None)
    price_max: float | None = Field(None)
    mileage_km: int | None = Field(None)
    features: str | None = Field(None)
    dealer_id: str = Field(...)


class CarSearchResult(BaseModel):
    """Result of a car search query."""

    status: str = Field(
        ...,
        description="Search status: found, not_found, or multiple.",
    )
    cars: list[CarRecord] = Field(
        default_factory=list,
        description="Matching car records (empty for not_found, one for found, multiple for multiple).",
    )
    candidates: list[CarRecord] | None = Field(
        None,
        description="Candidate list for disambiguation when status=multiple.",
    )
