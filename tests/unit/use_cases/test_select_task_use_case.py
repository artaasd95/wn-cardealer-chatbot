"""Tests for application/use_cases/select_task.py."""

from __future__ import annotations

import pytest

from application.use_cases.select_task import SelectTaskUseCase
from domain.enums.task_type import TaskType
from domain.enums.workflow_state import WorkflowState
from models.inputs.task import TaskDecision
from tests.fakes import FakeLLM, task_decision

pytestmark = pytest.mark.unit


class TestSelectTaskUseCase:
    """Intent extraction plus routing: happy paths and every rejection branch."""

    def test_routes_item_lookup(self, fake_llm: FakeLLM) -> None:
        """Happy path: an ITEM_LOOKUP decision routes to the lookup task."""
        fake_llm.enqueue(task_decision("ITEM_LOOKUP", 0.95))

        assert SelectTaskUseCase(fake_llm).execute("bmw 3 series", WorkflowState.START) == (
            TaskType.ITEM_LOOKUP
        )
        assert "bmw 3 series" in fake_llm.prompts[0]

    def test_routes_dealer_details_from_awaiting_action(self, fake_llm: FakeLLM) -> None:
        """Happy path: DEALER_DETAILS is allowed once a car is selected."""
        fake_llm.enqueue(task_decision("DEALER_DETAILS", 0.9))

        result = SelectTaskUseCase(fake_llm).execute(
            "dealer details", WorkflowState.AWAITING_ACTION
        )

        assert result == TaskType.DEALER_DETAILS

    def test_routes_schedule_call_from_awaiting_action(self, fake_llm: FakeLLM) -> None:
        """Happy path: SCHEDULE_CALL is allowed once a car is selected."""
        fake_llm.enqueue(task_decision("SCHEDULE_CALL", 0.9))

        result = SelectTaskUseCase(fake_llm).execute("book a call", WorkflowState.AWAITING_ACTION)

        assert result == TaskType.SCHEDULE_CALL

    def test_low_confidence_is_unknown(self, fake_llm: FakeLLM) -> None:
        """Failure branch: below the confidence floor, never a guess."""
        fake_llm.enqueue(task_decision("ITEM_LOOKUP", 0.2))

        assert SelectTaskUseCase(fake_llm).execute("hmm", WorkflowState.START) == TaskType.UNKNOWN

    def test_injected_task_type_is_unknown(self, fake_llm: FakeLLM) -> None:
        """Failure branch: an invented task type is rejected, never routed."""
        fake_llm.enqueue(task_decision("DELETE_ALL_CARS", 0.99))

        assert SelectTaskUseCase(fake_llm).execute("x", WorkflowState.START) == TaskType.UNKNOWN

    def test_state_guard_rejects_item_lookup_after_completion(self, fake_llm: FakeLLM) -> None:
        """Failure branch: a task refused from the current state routes UNKNOWN."""
        fake_llm.enqueue(task_decision("ITEM_LOOKUP", 0.99))

        result = SelectTaskUseCase(fake_llm).execute("find another car", WorkflowState.COMPLETE)

        assert result == TaskType.UNKNOWN

    def test_default_decision_is_unknown(self, fake_llm: FakeLLM) -> None:
        """Failure branch: an unscripted provider answer degrades to UNKNOWN."""
        decision = TaskDecision()
        assert decision.task_type == "UNKNOWN"

        assert SelectTaskUseCase(fake_llm).execute("anything", WorkflowState.START) == (
            TaskType.UNKNOWN
        )
