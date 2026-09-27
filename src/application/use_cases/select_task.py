"""Select task use case.

Calls the LLM to extract intent and routes to the appropriate task.
"""

from __future__ import annotations

import logging

from application.chat.task_router import TaskRouter
from domain.enums.task_type import TaskType
from domain.enums.workflow_state import WorkflowState
from infrastructure.llm.prompts.intent import build_intent_prompt, parse_task_decision
from models.inputs.task import TaskDecision
from ports.llm import LLMPort

logger = logging.getLogger(__name__)


class SelectTaskUseCase:
    """Extract intent from user input and route to a task."""

    def __init__(self, llm: LLMPort) -> None:
        """Initialize with LLM dependency.

        Args:
            llm: LLMPort for intent extraction.
        """
        self.llm = llm

    def execute(
        self,
        user_message: str,
        current_state: WorkflowState,
        conversation_history: str = "",
    ) -> TaskType:
        """Extract intent and route to a task.

        Args:
            user_message: The user's input.
            current_state: The current workflow state.
            conversation_history: Optional recent conversation context.

        Returns:
            The task type to execute (or UNKNOWN if routing fails).
        """
        prompt = build_intent_prompt(user_message, conversation_history)

        decision = self.llm.structured_completion(prompt, TaskDecision)

        task_type = parse_task_decision(decision)

        # Route to task, respecting current state
        routed_task = TaskRouter.route(
            TaskDecision(
                task_type=task_type.value,
                confidence=decision.confidence,
                reason=decision.reason,
            ),
            current_state,
        )

        if routed_task == TaskType.UNKNOWN and current_state is WorkflowState.AWAITING_DATETIME:
            logger.info(
                "Routing UNKNOWN intent to SCHEDULE_CALL because the workflow is awaiting date/time"
            )
            return TaskType.SCHEDULE_CALL

        return routed_task
