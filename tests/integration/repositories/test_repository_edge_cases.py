"""Repository edge cases against the Phase 1 fixtures and adversarial CSVs.

Plan.md §3 "Database / infrastructure": missing CSV, empty CSV, malformed CSV,
duplicate records, invalid dealer reference, invalid car fields, query failure,
transaction failure and an unreachable database all surface as clear behaviour
— never as a crash that takes the process down.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from config.settings import DatabaseSettings
from domain.exceptions import ConfigError, DomainError
from infrastructure.database import database as database_module
from infrastructure.database.database import Database
from infrastructure.database.tables.base import Base
from infrastructure.repositories.car_repository import CarRepositoryImpl
from infrastructure.repositories.dealer_repository import DealerRepositoryImpl
from infrastructure.repositories.schedule_repository import ScheduleRepositoryImpl
from models.inputs.car import NormalizedCarQuery
from models.outputs.schedule import ScheduleRecord

pytestmark = pytest.mark.integration


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    """Write a CSV file.

    Args:
        path: Target file.
        header: Column names.
        rows: Data rows.
    """
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def _database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, data_dir: Path) -> Database:
    """Build a Database bound to a throwaway SQLite file and data dir.

    Args:
        tmp_path: pytest temp directory.
        monkeypatch: pytest monkeypatch fixture.
        data_dir: Directory the CSV loader must read from.

    Returns:
        The configured (not yet initialised) Database.
    """
    monkeypatch.setattr(database_module, "DATA_DIR", data_dir)
    settings = DatabaseSettings(_env_file=None, url=f"sqlite:///{tmp_path}/repo-edge.db")
    return Database(settings)


class TestCsvLoaderEdgeCases:
    """Missing / empty / malformed CSVs and duplicate rows."""

    def test_missing_csv_files_leave_empty_tables(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Edge: no fixtures at all → schema exists, tables are empty."""
        data_dir = tmp_path / "no-csvs"
        data_dir.mkdir()
        db = _database(tmp_path, monkeypatch, data_dir)

        db.init_schema(Base.metadata)

        repo = CarRepositoryImpl(db.SessionLocal)
        assert repo.search(NormalizedCarQuery(make="bmw")).status == "not_found"

    def test_empty_csv_files_load_zero_rows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Edge: header-only CSVs → empty tables, no error."""
        data_dir = tmp_path / "empty-csvs"
        data_dir.mkdir()
        _write_csv(
            data_dir / "dealers.csv",
            ["dealer_id", "dealer_name", "city", "state", "address", "phone", "email", "rating"],
            [],
        )
        _write_csv(
            data_dir / "cars.csv",
            [
                "car_id",
                "make",
                "model",
                "variant",
                "year",
                "fuel_type",
                "transmission",
                "body_type",
                "price_min",
                "price_max",
                "mileage_km",
                "features",
                "dealer_id",
            ],
            [],
        )
        db = _database(tmp_path, monkeypatch, data_dir)

        db.init_schema(Base.metadata)

        assert DealerRepositoryImpl(db.SessionLocal).get_by_id("D-001") is None

    def test_malformed_csv_fails_loudly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Edge: a garbled header is refused loudly, not loaded as garbage."""
        data_dir = tmp_path / "bad-csvs"
        data_dir.mkdir()
        _write_csv(data_dir / "dealers.csv", ["nonsense"], [["x"]])
        db = _database(tmp_path, monkeypatch, data_dir)

        with pytest.raises(KeyError):
            db.init_schema(Base.metadata)

    def test_duplicate_records_are_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Edge: duplicate primary keys never make it into the database."""
        data_dir = tmp_path / "dup-csvs"
        data_dir.mkdir()
        _write_csv(
            data_dir / "dealers.csv",
            ["dealer_id", "dealer_name", "city", "state", "address", "phone", "email", "rating"],
            [["D-001", "Dup", "Pune", "MH", "1 A", "+91-1", "a@example", "4.0"]] * 2,
        )
        db = _database(tmp_path, monkeypatch, data_dir)

        with pytest.raises(IntegrityError):
            db.init_schema(Base.metadata)

    def test_unreachable_database_fails_fast(self) -> None:
        """Edge: a bad DATABASE_URL is a ConfigError at startup."""
        with pytest.raises(ConfigError):
            Database(DatabaseSettings(_env_file=None, url="not-a-database-url"))


class TestSeededEdgeCaseRows:
    """The deliberately awkward rows in the generated fixtures."""

    def test_car_with_missing_dealer_stays_searchable(self) -> None:
        """C-9004 points at the missing dealer D-999: car yes, dealer no."""
        db = Database(DatabaseSettings(_env_file=None, url="sqlite:///:memory:"))
        db.init_schema(Base.metadata)

        car = CarRepositoryImpl(db.SessionLocal).get_by_id("C-9004")
        dealer = DealerRepositoryImpl(db.SessionLocal).get_by_id("D-999")

        assert car is not None
        assert car.dealer_id == "D-999"
        assert dealer is None

    def test_car_with_invalid_numeric_fields_loads_partial_data(self) -> None:
        """C-9002 has underscores in its prices and no variant: partial row."""
        db = Database(DatabaseSettings(_env_file=None, url="sqlite:///:memory:"))
        db.init_schema(Base.metadata)

        car = CarRepositoryImpl(db.SessionLocal).get_by_id("C-9002")

        assert car is not None
        assert car.variant is None
        assert car.price_min is None
        assert car.price_max is None

    def test_dealer_with_missing_email_maps_to_partial_record(self) -> None:
        """D-012 has no email: the record is partial, never a validation crash."""
        db = Database(DatabaseSettings(_env_file=None, url="sqlite:///:memory:"))
        db.init_schema(Base.metadata)

        dealer = DealerRepositoryImpl(db.SessionLocal).get_by_id("D-012")

        assert dealer is not None
        assert dealer.dealer_name == "Apex AutoCare"
        assert dealer.email == ""

    def test_dealer_without_cars_still_reports_details(self) -> None:
        """D-013 sells nothing: details come back with an empty car list."""
        db = Database(DatabaseSettings(_env_file=None, url="sqlite:///:memory:"))
        db.init_schema(Base.metadata)

        with_cars = DealerRepositoryImpl(db.SessionLocal).get_with_cars("D-013")

        assert with_cars is not None
        assert with_cars.dealer.dealer_id == "D-013"
        assert with_cars.cars == []

    def test_search_finds_the_seeded_unique_row(self) -> None:
        """The single Nissan Kicks of 2023 (C-9002) is a one-result search."""
        db = Database(DatabaseSettings(_env_file=None, url="sqlite:///:memory:"))
        db.init_schema(Base.metadata)

        result = CarRepositoryImpl(db.SessionLocal).search(
            NormalizedCarQuery(make="nissan", model="kicks", year_from=2023, year_to=2023)
        )

        assert result.status == "found"
        assert result.cars[0].car_id == "C-9002"


class TestFailureSurfaces:
    """Query and transaction failures surface as domain-level behaviour."""

    def test_query_failure_propagates(self) -> None:
        """A broken session factory is not swallowed by the repository."""

        def _broken_session() -> None:
            raise RuntimeError("database unavailable")

        repo = CarRepositoryImpl(_broken_session)  # type: ignore[arg-type]

        with pytest.raises(RuntimeError, match="database unavailable"):
            repo.search(NormalizedCarQuery(make="bmw"))

    def test_transaction_failure_becomes_domain_error(self) -> None:
        """A failed insert maps to DomainError, not an SQLAlchemy leak."""

        def _broken_session() -> None:
            raise RuntimeError("transaction failed")

        repo = ScheduleRepositoryImpl(_broken_session)  # type: ignore[arg-type]
        record = ScheduleRecord(
            schedule_id="S-1",
            session_id="sess-1",
            dealer_id="D-003",
            car_id="C-0003",
            scheduled_for=datetime(2030, 5, 15, 15, 0),
            timezone="UTC",
        )

        with pytest.raises(DomainError, match="Could not store the schedule"):
            repo.save(record)
