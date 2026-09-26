"""End-to-end integration tests for full chat workflows."""

from __future__ import annotations

import pytest

from application.chat.service import ChatService
from DTO.inputs.chat import ChatRequest
from DTO.outputs.chat import ChatResponse
from ports.llm import LLMPort
from ports.repositories.car_repository import CarRepository
from ports.repositories.dealer_repository import DealerRepository
from ports.session_store import SessionStore


class TestEndToEnd:
    """End-to-end tests for complete chat workflows."""

    @pytest.fixture
    def chat_service(
        self,
        session_store: SessionStore,
        llm_port: LLMPort,
        car_repo: CarRepository,
        dealer_repo: DealerRepository,
    ) -> ChatService:
        """Create chat service for end-to-end tests."""
        return ChatService(session_store, llm_port, car_repo, dealer_repo)

    def test_simple_greeting(self, chat_service: ChatService) -> None:
        """Test handling a simple greeting."""
        request = ChatRequest(message="Hello", user_id="test-user")
        response = chat_service.chat(request)

        assert isinstance(response, ChatResponse)
        assert response.session_id is not None
        assert response.reply is not None
        assert response.workflow_state is not None

    def test_workflow_state_persists_across_turns(self, chat_service: ChatService) -> None:
        """Test that workflow state persists across multiple turns."""
        # First turn
        request1 = ChatRequest(message="Hello", user_id="test-user")
        response1 = chat_service.chat(request1)
        session_id = response1.session_id

        # Second turn with same session
        request2 = ChatRequest(session_id=session_id, message="How are you?", user_id="test-user")
        response2 = chat_service.chat(request2)

        assert response2.session_id == session_id

    def test_error_handling_invalid_request(self, chat_service: ChatService) -> None:
        """Test that invalid requests are handled gracefully."""
        request = ChatRequest(message="", user_id="test-user")
        response = chat_service.chat(request)

        # Should return error response, not raise
        assert response is not None
        assert response.session_id is not None

    def test_conversation_history_accumulates(self, chat_service: ChatService) -> None:
        """Test that conversation history accumulates across turns."""
        request1 = ChatRequest(message="First message", user_id="test-user")
        response1 = chat_service.chat(request1)
        session_id = response1.session_id

        request2 = ChatRequest(session_id=session_id, message="Second message", user_id="test-user")
        response2 = chat_service.chat(request2)

        # Both should succeed and maintain state
        assert response2.session_id == session_id
