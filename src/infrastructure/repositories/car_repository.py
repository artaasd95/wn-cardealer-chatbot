"""Car repository implementation.

Reads come from the SQLAlchemy session factory (one short-lived session per
operation) and are alias-aware: `data/aliases.csv` is loaded once at
construction so a user typing "B.M.W.", "Merc" or "C Class" resolves to the
canonical catalog value before the SQL filter is built.
"""

from __future__ import annotations

import csv
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import or_
from sqlalchemy.orm import Session

from infrastructure.database.tables.car import Car
from models.inputs.car import NormalizedCarQuery
from models.outputs.car import CarRecord, CarSearchResult
from ports.repositories.car_repository import CarRepository

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def _norm(value: str | None) -> str | None:
    """Normalize a catalog/alias value: trim + lowercase."""
    if value is None:
        return None
    stripped = value.strip().lower()
    return stripped or None


@dataclass(frozen=True)
class AliasRow:
    """One row of data/aliases.csv, normalized."""

    alias: str
    alias_type: str
    make: str | None
    model: str | None
    variant: str | None


def load_aliases(csv_path: Path | None = None) -> list[AliasRow]:
    """Load alias rows from data/aliases.csv.

    Args:
        csv_path: Optional explicit path; defaults to data/aliases.csv.

    Returns:
        Normalized alias rows, or an empty list when the file is absent.
    """
    path = csv_path or (DATA_DIR / "aliases.csv")
    if not path.exists():
        logger.info("aliases file %s not found; alias expansion disabled", path)
        return []

    rows: list[AliasRow] = []
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            for raw in csv.DictReader(handle):
                alias = _norm(raw.get("alias"))
                if not alias:
                    continue
                rows.append(
                    AliasRow(
                        alias=alias,
                        alias_type=(raw.get("alias_type") or "").strip().lower(),
                        make=_norm(raw.get("make")),
                        model=_norm(raw.get("model")),
                        variant=_norm(raw.get("variant")),
                    )
                )
    except OSError as exc:
        logger.warning("could not read aliases from %s: %s", path, exc)
        return []

    logger.info("loaded %d alias rows from %s", len(rows), path)
    return rows


class CarRepositoryImpl(CarRepository):
    """SQLAlchemy-based car repository."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        """Initialize with a session factory.

        Args:
            session_factory: A callable (typically ``database.SessionLocal``)
                that produces a SQLAlchemy Session per operation.
        """
        self._session_factory = session_factory
        self._aliases = load_aliases()

    # -- alias helpers -------------------------------------------------------

    def search_by_alias(self, alias: str) -> list[str]:
        """Look up normalized forms of an alias.

        Args:
            alias: An alias (make, model, or variant).

        Returns:
            List of normalized canonical forms the alias maps to,
            or an empty list if the alias is not recognized.
        """
        key = _norm(alias)
        if not key:
            return []

        forms: set[str] = {key}
        for row in self._aliases:
            if row.alias != key:
                continue
            for canonical in (row.make, row.model, row.variant):
                if canonical:
                    forms.add(canonical)

        return sorted(forms)

    def _field_terms(self, field: str, value: str) -> set[str]:
        """Expand one typed value into the terms that may appear in the catalog.

        Args:
            field: One of ``make``, ``model``, ``variant``.
            value: The (already normalized) value the user asked for.

        Returns:
            The value itself plus every canonical form it is an alias of.
        """
        key = _norm(value) or ""
        terms = {key}
        for row in self._aliases:
            if row.alias != key:
                continue
            canonical = getattr(row, field)
            if canonical:
                terms.add(canonical)
        return terms

    def _compound_model_terms(self, typed_make: str) -> set[str]:
        """Resolve a compound alias typed as the make (e.g. "BMW 3 Series").

        Args:
            typed_make: The make string the user typed.

        Returns:
            Model terms implied by an exact compound alias match, if any.
        """
        key = _norm(typed_make) or ""
        terms: set[str] = set()
        for row in self._aliases:
            if row.alias == key and row.model and row.alias_type == "model":
                terms.add(row.model)
        return terms

    # -- queries -------------------------------------------------------------

    def search(self, query: NormalizedCarQuery) -> CarSearchResult:
        """Search for cars matching the normalized query.

        Args:
            query: Normalized car search query.

        Returns:
            CarSearchResult with status and matching cars.
        """
        make_terms = self._field_terms("make", query.make) if query.make else set()
        model_terms = self._field_terms("model", query.model) if query.model else set()
        variant_terms = self._field_terms("variant", query.variant) if query.variant else set()

        # "BMW 3 Series" typed as a make also pins the model.
        if query.make and not query.model:
            model_terms |= self._compound_model_terms(query.make)

        with self._session_factory() as session:
            q = session.query(Car)

            if make_terms:
                q = q.filter(or_(*(Car.make.ilike(f"%{term}%") for term in make_terms)))
            if model_terms:
                q = q.filter(or_(*(Car.model.ilike(f"%{term}%") for term in model_terms)))
            if variant_terms:
                q = q.filter(or_(*(Car.variant.ilike(f"%{term}%") for term in variant_terms)))
            if query.year_from is not None:
                q = q.filter(Car.year >= query.year_from)
            if query.year_to is not None:
                q = q.filter(Car.year <= query.year_to)

            cars = q.all()
            # Build the records while the session is still open: the context
            # manager closes (and expires) the session on the way out.
            records = [self._car_record(car) for car in cars]

        if len(records) == 0:
            return CarSearchResult(status="not_found", cars=[], candidates=[])

        if len(records) == 1:
            return CarSearchResult(status="found", cars=records, candidates=[])

        # Multiple matches: return all cars and a reduced candidate list
        return CarSearchResult(
            status="multiple",
            cars=records,
            candidates=records[:5],  # Show up to 5 for disambiguation
        )

    def get_by_id(self, car_id: str) -> CarRecord | None:
        """Retrieve a car by ID.

        Args:
            car_id: The car identifier.

        Returns:
            CarRecord if found, None if not found.
        """
        with self._session_factory() as session:
            car = session.query(Car).filter(Car.car_id == car_id).first()
            return self._car_record(car) if car else None

    @staticmethod
    def _car_record(car: Car) -> CarRecord:
        """Convert a Car ORM object to a CarRecord DTO.

        Args:
            car: SQLAlchemy Car instance.

        Returns:
            CarRecord DTO.
        """
        return CarRecord(
            car_id=car.car_id,
            make=car.make,
            model=car.model,
            variant=car.variant,
            year=car.year,
            fuel_type=car.fuel_type,
            transmission=car.transmission,
            body_type=car.body_type,
            price_min=car.price_min,
            price_max=car.price_max,
            mileage_km=car.mileage_km,
            features=car.features,
            dealer_id=car.dealer_id,
        )
