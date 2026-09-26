from __future__ import annotations

from pydantic import BaseModel, Field

"""Internal models for car extraction and lookup."""


class CarExtraction(BaseModel):
    """Raw LLM output: extracted car attributes from user input."""

    make: str | None = Field(
        None,
        description="Extracted make, or None if not mentioned.",
    )
    model: str | None = Field(
        None,
        description="Extracted model, or None if not mentioned.",
    )
    variant: str | None = Field(
        None,
        description="Extracted variant/trim, or None if not mentioned.",
    )
    year_from: int | None = Field(
        None,
        description="Extracted min year, or None if not constrained.",
    )
    year_to: int | None = Field(
        None,
        description="Extracted max year, or None if not constrained.",
    )


class NormalizedCarQuery(BaseModel):
    """Post-normalization car query ready for database lookup."""

    make: str | None = Field(
        None,
        description="Normalized make.",
    )
    model: str | None = Field(
        None,
        description="Normalized model.",
    )
    variant: str | None = Field(
        None,
        description="Normalized variant.",
    )
    year_from: int | None = Field(
        None,
        description="Year from filter.",
    )
    year_to: int | None = Field(
        None,
        description="Year to filter.",
    )
