"""Chat service facade.

Entry point for all chat operations. Delegates to use cases.
"""

from __future__ import annotations

from application.use_cases.handle_user_message import HandleUserMessageUseCase
from DTO.inputs.chat import ChatRequest
from DTO.outputs.chat import ChatResponse
from ports.llm import LLMPort
from ports.repositories.car_repository import CarRepository
from ports.repositories.dealer_repository import DealerRepository
from ports.repositories.schedule_repository import ScheduleRepository
from ports.session_store import SessionStore


class ChatService:
    """Facade for chat operations."""

    def __init__(
        self,
        session_store: SessionStore,
        llm: LLMPort,
        car_repo: CarRepository,
        dealer_repo: DealerRepository,
        schedule_repo: ScheduleRepository | None = None,
    ) -> None:
        """Initialize with all dependencies.

        Args:
            session_store: SessionStore for session persistence.
            llm: LLMPort for LLM calls.
            car_repo: CarRepository for car search.
            dealer_repo: DealerRepository for dealer lookup.
            schedule_repo: ScheduleRepository for persisting created schedules.
        """
        self.handle_message = HandleUserMessageUseCase(
            session_store, llm, car_repo, dealer_repo, schedule_repo
        )

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Handle a chat message.

        Args:
            request: The incoming chat request.

        Returns:
            A ChatResponse with the system's reply and updated state.
        """
        return self.handle_message.execute(request)
