from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

"""Data Transfer Objects for car search request boundary."""


class CarSearchRequest(BaseModel):
    """Car search filter, extracted from user input."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "make": "BMW",
                "model": "3-Series",
                "variant": "xDrive",
                "year_from": 2020,
                "year_to": 2024,
            }
        }
    )

    make: str | None = Field(
        None,
        description="Car manufacturer (e.g., BMW, Mercedes-Benz).",
    )
    model: str | None = Field(
        None,
        description="Model name (e.g., 3-Series, C-Class).",
    )
    variant: str | None = Field(
        None,
        description="Optional trim/variant (e.g., xDrive, AMG).",
    )
    year_from: int | None = Field(
        None,
        ge=1900,
        le=2100,
        description="Minimum year, or None for no lower bound.",
    )
    year_to: int | None = Field(
        None,
        ge=1900,
        le=2100,
        description="Maximum year, or None for no upper bound.",
    )
