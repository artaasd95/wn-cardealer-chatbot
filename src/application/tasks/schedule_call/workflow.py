"""Schedule call workflow state machine.

Manages state transitions for the schedule call task:

    AWAITING_ACTION ──► SCHEDULE_CONFIRMED  (schedule record created and saved)
    AWAITING_ACTION ──► AWAITING_DATETIME    (date/time missing, ambiguous, in
                                              the past, or unparsable — the bot
                                              asks for the missing piece)

SCHEDULE_CONFIRMED (not COMPLETE) is the session state, so the turn can still
suggest its next tasks. COMPLETE stays reserved for the end of the
conversation and is gated in the state machine.
"""

from __future__ import annotations

from domain.enums.workflow_state import WorkflowState


class ScheduleCallWorkflow:
    """State machine for call scheduling."""

    @staticmethod
    def advance(schedule_created: bool) -> WorkflowState:
        """Advance workflow state based on schedule creation result.

        Args:
            schedule_created: True if a schedule record was created and saved.

        Returns:
            The next workflow state.
        """
        if schedule_created:
            return WorkflowState.SCHEDULE_CONFIRMED

        return WorkflowState.AWAITING_DATETIME
