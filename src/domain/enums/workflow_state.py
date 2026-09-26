from __future__ import annotations

from enum import Enum

"""Workflow state enumeration for the conversation state machine."""


class WorkflowState(str, Enum):
    """Enumeration of valid workflow states."""

    START = "START"
    """Initial state; user has just opened the chat."""

    AWAITING_CAR = "AWAITING_CAR"
    """Bot is waiting for car search criteria."""

    CAR_SELECTED = "CAR_SELECTED"
    """User has selected a car; ready for next action."""

    CAR_NOT_FOUND = "CAR_NOT_FOUND"
    """No cars matched the search; user can retry."""

    AWAITING_ACTION = "AWAITING_ACTION"
    """Car selected; user choosing between dealer details or schedule."""

    AWAITING_DEALER_DETAILS = "AWAITING_DEALER_DETAILS"
    """Bot is fetching dealer information."""

    DEALER_DETAILS_SHOWN = "DEALER_DETAILS_SHOWN"
    """Dealer details displayed; user can schedule or search again."""

    AWAITING_DATETIME = "AWAITING_DATETIME"
    """Bot is collecting date/time for scheduling."""

    SCHEDULE_CONFIRMED = "SCHEDULE_CONFIRMED"
    """Call has been scheduled successfully."""

    COMPLETE = "COMPLETE"
    """Conversation ended; user may restart."""

    def __str__(self) -> str:
        """Return the enum value as string."""
        return self.value
