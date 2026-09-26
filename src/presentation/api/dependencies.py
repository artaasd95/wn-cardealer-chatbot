"""Dependency injection for FastAPI routes.

Wires together LLM factory, repositories, and session store.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from application.chat.service import ChatService
from config.settings import Settings
from infrastructure.database.database import Database
from infrastructure.database.tables.base import Base
from infrastructure.llm.factory import LLMClientFactory
from infrastructure.repositories.car_repository import CarRepositoryImpl
from infrastructure.repositories.dealer_repository import DealerRepositoryImpl
from infrastructure.repositories.schedule_repository import ScheduleRepositoryImpl
from infrastructure.session.in_memory import InMemorySessionStore
from ports.llm import LLMPort
from ports.repositories.car_repository import CarRepository
from ports.repositories.dealer_repository import DealerRepository
from ports.repositories.schedule_repository import ScheduleRepository
from ports.session_store import SessionStore

logger = logging.getLogger(__name__)


class AppDependencies:
    """Container for application dependencies."""

    _instance: AppDependencies | None = None

    def __init__(self, settings: Settings) -> None:
        """Initialize dependencies.

        Args:
            settings: Application settings.
        """
        self.settings = settings

        # Initialize LLM (fail fast on config error)
        self.llm: LLMPort = LLMClientFactory.create(settings.llm_settings)
        logger.info(f"LLM initialized: {settings.llm_settings.provider}")

        # Initialize database
        self.database = Database(settings.database_settings)
        self.database.init_schema(Base.metadata)
        logger.info("Database initialized")

        # Initialize repositories
        self.car_repo: CarRepository = CarRepositoryImpl(self.database.SessionLocal)
        self.dealer_repo: DealerRepository = DealerRepositoryImpl(self.database.SessionLocal)
        self.schedule_repo: ScheduleRepository = ScheduleRepositoryImpl(self.database.SessionLocal)
        logger.info("Repositories initialized")

        # Initialize session store
        self.session_store: SessionStore = InMemorySessionStore()
        logger.info("Session store initialized")

        # Initialize chat service
        self.chat_service = ChatService(
            self.session_store, self.llm, self.car_repo, self.dealer_repo, self.schedule_repo
        )
        logger.info("Chat service initialized")

    @classmethod
    def get_instance(cls, settings: Settings) -> AppDependencies:
        """Get or create singleton instance.

        Args:
            settings: Application settings.

        Returns:
            The singleton AppDependencies instance.
        """
        if cls._instance is None:
            cls._instance = cls(settings)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        if cls._instance is not None:
            cls._instance.database.close()
        cls._instance = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get application settings (cached).

    Returns:
        The application settings.
    """
    return Settings()


def get_dependencies() -> AppDependencies:
    """Get application dependencies.

    Returns:
        The application dependencies instance.
    """
    settings = get_settings()
    return AppDependencies.get_instance(settings)
