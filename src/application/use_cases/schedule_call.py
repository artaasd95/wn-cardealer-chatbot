"""Schedule call use case.

Orchestrates the scheduling workflow: extract date/time, validate, create schedule.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

from application.tasks.schedule_call.workflow import ScheduleCallWorkflow
from domain.enums.workflow_state import WorkflowState
from domain.exceptions import InvalidScheduleError
from infrastructure.llm.prompts.schedule_extraction import (
    build_schedule_extraction_prompt,
)
from models.inputs.schedule import ScheduleExtraction
from models.outputs.schedule import ScheduleRecord
from ports.llm import LLMPort

logger = logging.getLogger(__name__)


class ScheduleCallUseCase:
    """Execute call scheduling workflow."""

    def __init__(self, llm: LLMPort) -> None:
        """Initialize with LLM dependency.

        Args:
            llm: LLMPort for schedule extraction.
        """
        self.llm = llm

    def execute(
        self,
        user_message: str,
        dealer_id: str,
        car_id: str,
        session_id: str,
    ) -> tuple[ScheduleRecord | None, WorkflowState]:
        """Execute schedule call workflow.

        Args:
            user_message: The user's raw input about scheduling.
            dealer_id: The selected dealer ID.
            car_id: The selected car ID.
            session_id: The session ID for reference.

        Returns:
            Tuple of (schedule record or None, next workflow state).
        """
        # Step 1: Extract date/time via LLM
        prompt = build_schedule_extraction_prompt(user_message)
        extraction = self.llm.structured_completion(prompt, ScheduleExtraction)

        # Step 2: Validate extraction
        if not extraction.date_raw or not extraction.time_raw:
            logger.warning(
                f"Incomplete schedule extraction: date={extraction.date_raw}, "
                f"time={extraction.time_raw}"
            )
            raise InvalidScheduleError("Please provide both a date and time for the call.")

        # Step 3: Parse date/time (simplified: assume valid for now)
        try:
            # In a real system, parse extraction.date_raw and extraction.time_raw
            # For now, use a placeholder (today at 14:00)
            scheduled_for = datetime.utcnow().replace(hour=14, minute=0, second=0)

            # Step 4: Validate not in the past
            if scheduled_for < datetime.utcnow():
                logger.warning(f"Scheduled time is in the past: {scheduled_for}")
                raise InvalidScheduleError(
                    "The scheduled time cannot be in the past. Please choose a future date and time."
                )

        except InvalidScheduleError:
            raise
        except Exception as e:
            logger.error(f"Failed to parse schedule: {str(e)}")
            raise InvalidScheduleError(f"Invalid date/time: {str(e)}") from e

        # Step 5: Create schedule record
        schedule = ScheduleRecord(
            schedule_id=str(uuid4()),
            session_id=session_id,
            dealer_id=dealer_id,
            car_id=car_id,
            scheduled_for=scheduled_for,
            timezone=extraction.timezone or "UTC",
            status="pending",
        )

        next_state = ScheduleCallWorkflow.advance(schedule_created=True)

        return schedule, next_state
