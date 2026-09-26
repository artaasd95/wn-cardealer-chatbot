"""Task router for intent classification.

Routes user input to one of three tasks based on LLM intent extraction.
Respects workflow state so the router cannot skip required steps.
"""

from __future__ import annotations

import logging

from domain.enums.task_type import TaskType
from domain.enums.workflow_state import WorkflowState
from models.inputs.task import TaskDecision

logger = logging.getLogger(__name__)


class TaskRouter:
    """Routes intent decisions to tasks, respecting workflow state."""

    # Legal transitions: from which states can we enter each task?
    TASK_ENTRY_STATES = {
        TaskType.ITEM_LOOKUP: {
            WorkflowState.START,
            WorkflowState.AWAITING_CAR,
            WorkflowState.CAR_NOT_FOUND,
        },
        TaskType.DEALER_DETAILS: {WorkflowState.AWAITING_ACTION},
        TaskType.SCHEDULE_CALL: {WorkflowState.AWAITING_ACTION},
    }

    @staticmethod
    def route(decision: TaskDecision, current_state: WorkflowState) -> TaskType:
        """Route a task decision to a task type.

        Args:
            decision: The LLM's task classification.
            current_state: The current workflow state.

        Returns:
            The task type to execute, or UNKNOWN if routing is invalid.
        """
        task_type = TaskType(decision.task_type)

        # Check if task is allowed from current state
        allowed_states = TaskRouter.TASK_ENTRY_STATES.get(task_type, set())
        if current_state not in allowed_states:
            logger.warning(
                f"Task {task_type} not allowed from state {current_state}. Routing to UNKNOWN."
            )
            return TaskType.UNKNOWN

        logger.info(f"Routing to {task_type} (confidence: {decision.confidence})")
        return task_type
