from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

"""Data Transfer Objects for dealer response boundary."""


class CarReference(BaseModel):
    """Minimal car reference for dealer context."""

    car_id: str = Field(...)
    make: str = Field(...)
    model: str = Field(...)
    year: int = Field(...)


class DealerDetails(BaseModel):
    """Complete dealer information."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "dealer_id": "D-001",
                "name": "Downtown BMW",
                "city": "New York",
                "address": "123 Main St, New York, NY 10001",
                "phone": "+1-555-0100",
                "email": "sales@downtownbmw.com",
                "rating": 4.7,
                "cars": [
                    {
                        "car_id": "C-001",
                        "make": "BMW",
                        "model": "3-Series",
                        "year": 2023,
                    }
                ],
            }
        }
    )

    dealer_id: str = Field(
        ...,
        description="Unique dealer identifier.",
    )
    name: str = Field(
        ...,
        description="Dealer name.",
    )
    city: str = Field(
        ...,
        description="City location.",
    )
    address: str = Field(
        ...,
        description="Full street address.",
    )
    phone: str = Field(
        ...,
        description="Contact phone number.",
    )
    email: str = Field(
        ...,
        description="Contact email address.",
    )
    rating: float | None = Field(
        None,
        ge=0.0,
        le=5.0,
        description="Optional rating (0–5 stars).",
    )
    cars: list[CarReference] = Field(
        default_factory=list,
        description="Cars available at this dealer.",
    )
