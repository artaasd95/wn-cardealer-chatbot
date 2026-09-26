"""Database initialization and session management.

This module sets up the SQLAlchemy engine and session factory,
creates all tables, and loads CSV fixtures on first run.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import DatabaseSettings
from domain.exceptions import ConfigError

logger = logging.getLogger(__name__)

# Single source of truth for where the CSV fixtures live. Tests point this at
# a temporary directory to exercise the missing / empty / malformed CSV edge
# cases without touching the real fixtures.
DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def _optional_str(value: str | None) -> str | None:
    """CSV cell → stripped string, or None when blank."""
    text = (value or "").strip()
    return text or None


def _optional_int(value: str | None) -> int | None:
    """CSV cell → int, or None when blank or unreadable."""
    text = (value or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _optional_float(value: str | None) -> float | None:
    """CSV cell → float, or None when blank or unreadable."""
    text = (value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


class Database:
    """Database engine and session factory."""

    def __init__(self, settings: DatabaseSettings) -> None:
        """Initialize the database with settings.

        Args:
            settings: Validated DatabaseSettings from config.

        Raises:
            ConfigError: If the database URL is invalid or connection fails.
        """
        try:
            self.engine = create_engine(
                settings.url,
                echo=settings.echo,
                connect_args={"check_same_thread": False} if "sqlite" in settings.url else {},
            )
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        except Exception as e:
            raise ConfigError(f"Failed to initialize database: {str(e)}") from e

    def init_schema(self, base_metadata: Any) -> None:  # noqa: ANN001
        """Create all tables and load CSV fixtures.

        Args:
            base_metadata: SQLAlchemy declarative base metadata object.
        """
        try:
            # Importing the package registers every table module
            # (car, dealer, session, message, schedule) on the metadata.
            import infrastructure.database.tables  # noqa: F401

            base_metadata.create_all(bind=self.engine)
            logger.info("Database tables created")
            self._load_csv_fixtures()
        except Exception as e:
            logger.error(f"Failed to initialize schema: {str(e)}")
            raise

    def _load_csv_fixtures(self) -> None:
        """Load CSV fixtures into the database if they exist and tables are empty.

        Loads data/cars.csv and data/dealers.csv.
        """
        from infrastructure.database.tables.car import Car
        from infrastructure.database.tables.dealer import Dealer

        data_dir = DATA_DIR

        if not data_dir.exists():
            logger.info("data/ directory not found; skipping CSV load")
            return

        cars_csv = data_dir / "cars.csv"
        dealers_csv = data_dir / "dealers.csv"

        with self.SessionLocal() as session:
            # Load dealers first (foreign key dependency)
            if dealers_csv.exists() and session.query(Dealer).count() == 0:
                try:
                    with open(dealers_csv, encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            session.add(
                                Dealer(
                                    dealer_id=row["dealer_id"],
                                    dealer_name=row["dealer_name"],
                                    city=_optional_str(row.get("city")),
                                    state=_optional_str(row.get("state")),
                                    address=_optional_str(row.get("address")),
                                    phone=_optional_str(row.get("phone")),
                                    email=_optional_str(row.get("email")),
                                    rating=_optional_float(row.get("rating")),
                                )
                            )
                    session.commit()
                    logger.info(
                        f"Loaded {session.query(Dealer).count()} dealers from {dealers_csv}"
                    )
                except Exception as e:
                    session.rollback()
                    logger.error(f"Failed to load dealers: {str(e)}")
                    raise

            # Load cars
            if cars_csv.exists() and session.query(Car).count() == 0:
                try:
                    with open(cars_csv, encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            session.add(
                                Car(
                                    car_id=row["car_id"],
                                    make=row["make"],
                                    model=row["model"],
                                    variant=_optional_str(row.get("variant")),
                                    year=_optional_int(row.get("year")),
                                    fuel_type=_optional_str(row.get("fuel_type")),
                                    transmission=_optional_str(row.get("transmission")),
                                    body_type=_optional_str(row.get("body_type")),
                                    price_min=_optional_int(row.get("price_min")),
                                    price_max=_optional_int(row.get("price_max")),
                                    mileage_km=_optional_int(row.get("mileage_km")),
                                    features=_optional_str(row.get("features")),
                                    dealer_id=row["dealer_id"],
                                )
                            )
                    session.commit()
                    logger.info(f"Loaded {session.query(Car).count()} cars from {cars_csv}")
                except Exception as e:
                    session.rollback()
                    logger.error(f"Failed to load cars: {str(e)}")
                    raise

    def get_session(self) -> Session:
        """Get a new database session.

        Returns:
            A SQLAlchemy Session instance.
        """
        return self.SessionLocal()
