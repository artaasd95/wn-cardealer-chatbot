"""Full turns over HTTP: lookup → dealer details → schedule.

These tests drive the real FastAPI app and the real repositories against the
Phase 1 CSV fixtures; only the LLM port is faked. Every assertion is about the
contract at the HTTP boundary: status codes, branch behaviour and the state
machine advancing legally.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from domain.enums.workflow_state import LEGAL_TRANSITIONS, WorkflowState
from models.inputs.car import CarExtraction
from models.inputs.response import ResponseWording
from models.inputs.schedule import ScheduleExtraction
from models.inputs.task import TaskDecision
from tests.fakes import FakeLLM, RaisingLLM

pytestmark = pytest.mark.integration


def _chat(client: TestClient, message: str, session_id: str | None = None) -> dict:
    """POST one chat turn.

    Args:
        client: The test client.
        message: The user message.
        session_id: Session to continue, or None for a fresh one.

    Returns:
        The response body.
    """
    response = client.post("/api/chat", json={"session_id": session_id, "message": message})
    assert response.status_code == 200, response.text
    return response.json()


def _assert_legal_step(current: str, nxt: str) -> None:
    """Assert one state transition is defined in the state machine.

    Args:
        current: The state before the turn.
        nxt: The state after the turn.
    """
    assert WorkflowState(nxt) in LEGAL_TRANSITIONS[WorkflowState(current)], (
        f"illegal transition {current} -> {nxt}"
    )


class TestFullTurnOverHttp:
    """Plan Phase 8: lookup → dealer details → schedule, legally."""

    def test_lookup_dealer_details_schedule(self, client: TestClient, fake_llm: FakeLLM) -> None:
        """The assignment's main flow end to end over HTTP."""
        # Turn 1 — item lookup, one match (BMW 3 Series 320i 2021 = C-0003)
        fake_llm.enqueue(_task("ITEM_LOOKUP"))
        fake_llm.enqueue(_car("BMW", "3 Series", "320i", 2021, 2021))
        first = _chat(client, "I'm looking for a BMW 3 Series 320i 2021")

        assert first["workflow_state"] == "AWAITING_ACTION"
        assert first["reply"].startswith("Found BMW 3 Series 320i (2021)")
        assert "Prestige Cars in Bangalore" in first["reply"]
        assert first["suggested_actions"] == [
            "Get dealer details",
            "Schedule a call",
            "Find another car",
        ]
        session_id = first["session_id"]

        # Turn 2 — dealer details
        fake_llm.enqueue(_task("DEALER_DETAILS"))
        fake_llm.enqueue(_wording(""))
        second = _chat(client, "show me the dealer details", session_id)

        assert second["workflow_state"] == "DEALER_DETAILS_SHOWN"
        assert "Prestige Cars (Bangalore)" in second["reply"]
        assert "Phone: +91-80-2552-1003" in second["reply"]
        _assert_legal_step(first["workflow_state"], second["workflow_state"])

        # Turn 3 — schedule the call
        fake_llm.enqueue(_task("SCHEDULE_CALL"))
        fake_llm.enqueue(_schedule("2030-05-15", "15:00", "UTC"))
        fake_llm.enqueue(_wording(""))
        third = _chat(client, "book a call for 2030-05-15 at 3pm UTC", session_id)

        assert third["workflow_state"] == "SCHEDULE_CONFIRMED"
        assert third["reply"].startswith("Your call is booked for")
        _assert_legal_step(second["workflow_state"], third["workflow_state"])

    def test_schedule_record_is_persisted(
        self, client: TestClient, fake_llm: FakeLLM, database_url: str
    ) -> None:
        """A confirmed call writes one local record — no external booking."""
        fake_llm.enqueue(_task("ITEM_LOOKUP"))
        fake_llm.enqueue(_car("BMW", "3 Series", "320i", 2021, 2021))
        first = _chat(client, "bmw 3 series 320i 2021")

        fake_llm.enqueue(_task("SCHEDULE_CALL"))
        fake_llm.enqueue(_schedule("2030-05-15", "15:00", "UTC"))
        fake_llm.enqueue(_wording(""))
        _chat(client, "book a call for 2030-05-15 at 3pm UTC", first["session_id"])

        engine = create_engine(database_url)
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT dealer_id, car_id, status FROM schedule")).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "D-003"
        assert rows[0][1] == "C-0003"
        assert rows[0][2] == "pending"


class TestBranchesOverHttp:
    """Plan Phase 8: 0-match and multi-match return branches, not 500s."""

    def test_zero_match_branch(self, client: TestClient, fake_llm: FakeLLM) -> None:
        """0 matches answer with the fallback message and CAR_NOT_FOUND."""
        fake_llm.enqueue(_task("ITEM_LOOKUP"))
        fake_llm.enqueue(_car("Ferrari", "F40", None, None, None))

        body = _chat(client, "Ferrari F40")

        assert body["workflow_state"] == "CAR_NOT_FOUND"
        assert "couldn't find a car matching that description" in body["reply"]
        assert body["suggested_actions"] == ["Find a car"]

    def test_multi_match_branch(self, client: TestClient, fake_llm: FakeLLM) -> None:
        """More than one match returns the disambiguation branch."""
        fake_llm.enqueue(_task("ITEM_LOOKUP"))
        fake_llm.enqueue(_car("BMW", "3 Series", None, None, None))

        body = _chat(client, "BMW 3 Series")

        assert body["workflow_state"] == "AWAITING_CAR"
        assert body["reply"].startswith("I found several matches.")
        assert len(body["suggested_actions"]) == 5
        assert body["suggested_actions"][0].startswith("BMW 3 Series")

    def test_car_with_missing_dealer_still_selects_the_car(
        self, client: TestClient, fake_llm: FakeLLM
    ) -> None:
        """Seeded edge row C-9004 -> D-999: the car is kept, the dealer is not."""
        fake_llm.enqueue(_task("ITEM_LOOKUP"))
        fake_llm.enqueue(_car("Tata", "Punch", "Creative S", 2024, 2024))

        body = _chat(client, "Tata Punch Creative S 2024")

        assert body["workflow_state"] == "CAR_SELECTED"
        assert body["reply"].startswith("Found Tata Punch Creative S (2024)")
        assert "can help you with it" not in body["reply"]

    def test_dealer_details_without_dealer_asks_to_pick_a_car(
        self, client: TestClient, fake_llm: FakeLLM
    ) -> None:
        """The guard answers in-band; the request never becomes a 500."""
        fake_llm.enqueue(_task("ITEM_LOOKUP"))
        fake_llm.enqueue(_car("Tata", "Punch", "Creative S", 2024, 2024))
        first = _chat(client, "Tata Punch Creative S 2024")

        fake_llm.enqueue(_task("DEALER_DETAILS"))
        second = _chat(client, "show me the dealer details", first["session_id"])

        assert second["reply"] == "No dealer selected. Please search for and select a car first."
        assert second["workflow_state"] == "CAR_SELECTED"

    def test_incomplete_dealer_row_returns_partial_details(
        self, client: TestClient, fake_llm: FakeLLM
    ) -> None:
        """Seeded edge row D-012 has no email: partial details, never a crash."""
        fake_llm.enqueue(_task("ITEM_LOOKUP"))
        fake_llm.enqueue(_car("Honda", "Amaze", "E", 2023, 2023))
        first = _chat(client, "Honda Amaze E 2023")
        assert first["workflow_state"] == "AWAITING_ACTION"

        fake_llm.enqueue(_task("DEALER_DETAILS"))
        fake_llm.enqueue(_wording(""))
        second = _chat(client, "dealer details", first["session_id"])

        assert "Apex AutoCare (Indore)" in second["reply"]
        assert "Phone: +91-731-2551-1012" in second["reply"]
        assert second["workflow_state"] == "DEALER_DETAILS_SHOWN"


class TestFailureOverHttp:
    """A dead provider produces a graceful reply rather than a 500."""

    def test_llm_outage_degrades_gracefully(self, build_app) -> None:
        """Timeout / API failure / rate limit: HTTP 200 with fallback wording."""
        with TestClient(build_app(RaisingLLM())) as outage_client:
            response = outage_client.post(
                "/api/chat", json={"session_id": None, "message": "bmw 3 series"}
            )

        assert response.status_code == 200
        body = response.json()
        assert body["reply"] == "An unexpected error occurred. Please try again."
        assert body["workflow_state"] == "ERROR"


# ---------------------------------------------------------------------------
# Scripted LLM responses shared by the tests above.
# ---------------------------------------------------------------------------


def _task(task_type: str) -> TaskDecision:
    """Build a scripted intent decision.

    Args:
        task_type: One of the TaskType values.

    Returns:
        The TaskDecision instance.
    """
    return TaskDecision(task_type=task_type, confidence=0.9, reason="scripted")


def _car(
    make: str,
    model: str,
    variant: str | None,
    year_from: int | None,
    year_to: int | None,
) -> CarExtraction:
    """Build a scripted car extraction.

    Args:
        make: Extracted make.
        model: Extracted model.
        variant: Extracted variant.
        year_from: Extracted lower year bound.
        year_to: Extracted upper year bound.

    Returns:
        The CarExtraction instance.
    """
    return CarExtraction(
        make=make, model=model, variant=variant, year_from=year_from, year_to=year_to
    )


def _schedule(
    date_raw: str | None, time_raw: str | None, timezone: str | None
) -> ScheduleExtraction:
    """Build a scripted schedule extraction.

    Args:
        date_raw: Extracted date text.
        time_raw: Extracted time text.
        timezone: Extracted timezone text.

    Returns:
        The ScheduleExtraction instance.
    """
    return ScheduleExtraction(date_raw=date_raw, time_raw=time_raw, timezone=timezone)


def _wording(reply: str) -> ResponseWording:
    """Build a scripted response wording (empty forces the deterministic text).

    Args:
        reply: The wording text.

    Returns:
        The ResponseWording instance.
    """
    return ResponseWording(reply=reply)
