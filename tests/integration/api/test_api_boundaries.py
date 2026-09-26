"""HTTP boundary behaviour: validation, health, session lifecycle."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from models.inputs.car import CarExtraction
from models.inputs.task import TaskDecision
from tests.fakes import FakeLLM

pytestmark = pytest.mark.integration


class TestRequestValidation:
    """Empty input, very long input and missing fields are 422s, not crashes."""

    def test_empty_message_is_rejected(self, client: TestClient) -> None:
        """Edge: an empty message never reaches the application."""
        response = client.post("/api/chat", json={"session_id": None, "message": ""})
        assert response.status_code == 422

    def test_whitespace_only_message_is_answered_gracefully(
        self, client: TestClient, fake_llm: FakeLLM
    ) -> None:
        """Edge: whitespace passes validation and degrades to a clarification."""
        response = client.post("/api/chat", json={"session_id": None, "message": "   "})
        assert response.status_code == 200
        assert response.json()["reply"].startswith("I didn't understand that.")

    def test_maximum_length_message_is_accepted(
        self, client: TestClient, fake_llm: FakeLLM
    ) -> None:
        """Boundary: exactly 2000 characters is still a valid message."""
        fake_llm.enqueue(TaskDecision(task_type="UNKNOWN", confidence=0.4))
        response = client.post("/api/chat", json={"session_id": None, "message": "a" * 2000})
        assert response.status_code == 200

    def test_overlong_message_is_rejected(self, client: TestClient) -> None:
        """Boundary: 2001 characters is rejected at the DTO boundary."""
        response = client.post("/api/chat", json={"session_id": None, "message": "a" * 2001})
        assert response.status_code == 422

    def test_missing_message_field_is_rejected(self, client: TestClient) -> None:
        """Edge: a request without a message is a validation error."""
        response = client.post("/api/chat", json={"session_id": None})
        assert response.status_code == 422


class TestHealth:
    """GET /health reports liveness and the provider name, never the key."""

    def test_health_reports_provider_without_leaking_the_key(self, client: TestClient) -> None:
        """Plan: provider name yes, api key never."""
        response = client.get("/api/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["llm_provider"] == "openai_compatible"
        assert "sk-" not in str(body)


class TestSessionLifecycle:
    """DELETE /sessions/{id} covers the restart-conversation path."""

    def test_deleted_session_starts_over(self, client: TestClient, fake_llm: FakeLLM) -> None:
        """Edge: after a restart the conversation begins from START again."""
        fake_llm.enqueue(TaskDecision(task_type="ITEM_LOOKUP", confidence=0.9))
        fake_llm.enqueue(
            CarExtraction(make="BMW", model="3 Series", variant="320i", year_from=2021)
        )
        first = client.post(
            "/api/chat", json={"session_id": None, "message": "bmw 3 series 320i"}
        ).json()
        session_id = first["session_id"]
        assert first["workflow_state"] == "AWAITING_ACTION"

        deleted = client.delete(f"/api/sessions/{session_id}")
        assert deleted.status_code == 204

        # The old id is gone: the next turn is a brand-new session.
        fake_llm.enqueue(TaskDecision(task_type="UNKNOWN", confidence=0.9))
        second = client.post(
            "/api/chat", json={"session_id": session_id, "message": "hello again"}
        ).json()
        assert second["session_id"] != session_id
        assert second["workflow_state"] == "START"

    def test_unknown_session_id_is_never_an_error(
        self, client: TestClient, fake_llm: FakeLLM
    ) -> None:
        """Edge: an invalid session id silently becomes a fresh session."""
        fake_llm.enqueue(TaskDecision(task_type="UNKNOWN", confidence=0.9))
        body = client.post(
            "/api/chat", json={"session_id": "no-such-session", "message": "hello"}
        ).json()

        assert body["session_id"] != "no-such-session"
        assert body["workflow_state"] == "START"
