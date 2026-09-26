"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.settings import Settings
from infrastructure.database.database import Database
from infrastructure.database.tables.base import Base
from infrastructure.llm.factory import LLMClientFactory
from infrastructure.repositories.car_repository import CarRepositoryImpl
from infrastructure.repositories.dealer_repository import DealerRepositoryImpl
from infrastructure.session.in_memory import InMemorySessionStore
from models.outputs.session import SessionRecord
from ports.llm import LLMPort
from ports.repositories.car_repository import CarRepository
from ports.repositories.dealer_repository import DealerRepository
from ports.session_store import SessionStore


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Get test settings from .env."""
    return Settings()


@pytest.fixture(scope="session")
def test_database(test_settings: Settings) -> Database:
    """Create test database with schema."""
    # Use in-memory SQLite for testing
    from config.settings import DatabaseSettings

    db_settings = DatabaseSettings(url="sqlite:///:memory:")
    db = Database(db_settings)
    db.init_schema(Base.metadata)
    return db


@pytest.fixture
def session_store() -> SessionStore:
    """Create fresh session store for each test."""
    return InMemorySessionStore()


@pytest.fixture
def car_repo(test_database: Database) -> CarRepository:
    """Create car repository."""
    return CarRepositoryImpl(test_database.SessionLocal)


@pytest.fixture
def dealer_repo(test_database: Database) -> DealerRepository:
    """Create dealer repository."""
    return DealerRepositoryImpl(test_database.SessionLocal)


@pytest.fixture
def llm_port(test_settings: Settings) -> LLMPort:
    """Create LLM port."""
    return LLMClientFactory.create(test_settings.llm_settings)


@pytest.fixture
def test_session_record(session_store: SessionStore) -> SessionRecord:
    """Create a test session record."""
    record = session_store.create(user_id="test-user")
    return record
