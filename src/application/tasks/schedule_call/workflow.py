"""Schedule call workflow state machine.

Manages state transitions for the schedule call task.
"""

from __future__ import annotations

from domain.enums.workflow_state import WorkflowState


class ScheduleCallWorkflow:
    """State machine for call scheduling."""

    @staticmethod
    def advance(schedule_created: bool) -> WorkflowState:
        """Advance workflow state based on schedule creation result.

        Args:
            schedule_created: True if schedule was created, False otherwise.

        Returns:
            The next workflow state.
        """
        if schedule_created:
            return WorkflowState.COMPLETE

        return WorkflowState.AWAITING_DATETIME
