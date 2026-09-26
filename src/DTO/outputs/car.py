from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

"""Data Transfer Objects for car response boundary."""


class CarSummary(BaseModel):
    """Summary of a single car."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "car_id": "C-001",
                "make": "BMW",
                "model": "3-Series",
                "variant": "xDrive",
                "year": 2023,
                "price_range": "$35,000 - $45,000",
            }
        }
    )

    car_id: str = Field(
        ...,
        description="Unique car identifier.",
    )
    make: str = Field(
        ...,
        description="Manufacturer name.",
    )
    model: str = Field(
        ...,
        description="Model name.",
    )
    variant: str | None = Field(
        None,
        description="Optional trim/variant.",
    )
    year: int = Field(
        ...,
        ge=1900,
        le=2100,
        description="Year of manufacture.",
    )
    price_range: str = Field(
        ...,
        description="Price range (e.g., '$25,000 - $35,000').",
    )


class CarCandidateList(BaseModel):
    """List of car candidates for disambiguation."""

    candidates: list[CarSummary] = Field(
        ...,
        description="List of matching cars.",
    )
    message: str = Field(
        ...,
        description="Message asking user to disambiguate.",
    )
