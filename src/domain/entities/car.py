from __future__ import annotations

from dataclasses import dataclass

from models.inputs.car import CarExtraction, NormalizedCarQuery

"""Car domain entity."""


@dataclass
class Car:
    """Domain entity representing a car."""

    car_id: str
    make: str
    model: str
    variant: str | None
    year: int
    fuel_type: str | None
    transmission: str | None
    body_type: str | None
    price_min: float | None
    price_max: float | None
    mileage_km: int | None
    features: str | None
    dealer_id: str

    @classmethod
    def normalize_extraction(cls, extraction: CarExtraction) -> NormalizedCarQuery:
        """Normalize raw LLM extraction into a lookup query.

        Args:
            extraction: Raw LLM output with make/model/variant/year fields.

        Returns:
            NormalizedCarQuery ready for repository search.
        """
        # Normalize strings: strip whitespace, standardize casing
        make = extraction.make.strip().title() if extraction.make else None
        model = extraction.model.strip().title() if extraction.model else None
        variant = extraction.variant.strip().title() if extraction.variant else None

        # Year bounds: ensure year_from <= year_to if both provided
        year_from = extraction.year_from
        year_to = extraction.year_to
        if year_from and year_to and year_from > year_to:
            year_from, year_to = year_to, year_from

        return NormalizedCarQuery(
            make=make,
            model=model,
            variant=variant,
            year_from=year_from,
            year_to=year_to,
        )

    def matches(self, query: NormalizedCarQuery) -> bool:
        """Check if this car matches the normalized query.

        Args:
            query: NormalizedCarQuery with optional filters.

        Returns:
            True if all non-None query fields match this car.
        """
        if query.make and self.make.lower() != query.make.lower():
            return False
        if query.model and self.model.lower() != query.model.lower():
            return False
        if query.variant and (
            self.variant is None or self.variant.lower() != query.variant.lower()
        ):
            return False
        if query.year_from and self.year < query.year_from:
            return False
        return not (query.year_to and self.year > query.year_to)

    def is_complete(self) -> bool:
        """Verify this car has all essential fields for display.

        Returns:
            True if car_id, make, model, year, and dealer_id are all present.
        """
        return bool(self.car_id and self.make and self.model and self.year and self.dealer_id)
