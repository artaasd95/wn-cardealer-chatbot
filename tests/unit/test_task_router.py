"""Tests for application/chat/task_router.py."""

from __future__ import annotations

from application.chat.task_router import TaskRouter
from domain.enums.task_type import TaskType
from domain.enums.workflow_state import WorkflowState
from models.inputs.task import TaskDecision


class TestTaskRouter:
    """Tests for TaskRouter."""

    def test_route_item_lookup_from_start(self) -> None:
        """Test routing ITEM_LOOKUP from START state."""
        decision = TaskDecision(
            task_type=TaskType.ITEM_LOOKUP.value,
            confidence=0.95,
            reason="User is searching for a car",
        )
        routed = TaskRouter.route(decision, WorkflowState.START)
        assert routed == TaskType.ITEM_LOOKUP

    def test_route_item_lookup_from_awaiting_car(self) -> None:
        """Test routing ITEM_LOOKUP from AWAITING_CAR state."""
        decision = TaskDecision(
            task_type=TaskType.ITEM_LOOKUP.value,
            confidence=0.90,
            reason="User refined their search",
        )
        routed = TaskRouter.route(decision, WorkflowState.AWAITING_CAR)
        assert routed == TaskType.ITEM_LOOKUP

    def test_route_dealer_details_from_awaiting_action(self) -> None:
        """Test routing DEALER_DETAILS from AWAITING_ACTION state."""
        decision = TaskDecision(
            task_type=TaskType.DEALER_DETAILS.value,
            confidence=0.85,
            reason="User wants dealer info",
        )
        routed = TaskRouter.route(decision, WorkflowState.AWAITING_ACTION)
        assert routed == TaskType.DEALER_DETAILS

    def test_route_schedule_call_from_awaiting_action(self) -> None:
        """Test routing SCHEDULE_CALL from AWAITING_ACTION state."""
        decision = TaskDecision(
            task_type=TaskType.SCHEDULE_CALL.value,
            confidence=0.88,
            reason="User wants to schedule",
        )
        routed = TaskRouter.route(decision, WorkflowState.AWAITING_ACTION)
        assert routed == TaskType.SCHEDULE_CALL

    def test_route_dealer_details_from_start_invalid(self) -> None:
        """Test that DEALER_DETAILS from START is routed to UNKNOWN."""
        decision = TaskDecision(
            task_type=TaskType.DEALER_DETAILS.value,
            confidence=0.80,
            reason="Invalid state",
        )
        routed = TaskRouter.route(decision, WorkflowState.START)
        assert routed == TaskType.UNKNOWN

    def test_route_schedule_call_from_start_invalid(self) -> None:
        """Test that SCHEDULE_CALL from START is routed to UNKNOWN."""
        decision = TaskDecision(
            task_type=TaskType.SCHEDULE_CALL.value,
            confidence=0.75,
            reason="Invalid state",
        )
        routed = TaskRouter.route(decision, WorkflowState.START)
        assert routed == TaskType.UNKNOWN

    def test_route_item_lookup_from_complete_invalid(self) -> None:
        """Test that ITEM_LOOKUP from COMPLETE is routed to UNKNOWN."""
        decision = TaskDecision(
            task_type=TaskType.ITEM_LOOKUP.value,
            confidence=0.70,
            reason="Workflow already complete",
        )
        routed = TaskRouter.route(decision, WorkflowState.COMPLETE)
        assert routed == TaskType.UNKNOWN

    def test_route_unknown_task(self) -> None:
        """Test routing UNKNOWN task."""
        decision = TaskDecision(
            task_type=TaskType.UNKNOWN.value,
            confidence=0.0,
            reason="Could not classify",
        )
        routed = TaskRouter.route(decision, WorkflowState.START)
        assert routed == TaskType.UNKNOWN
