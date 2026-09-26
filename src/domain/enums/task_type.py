from __future__ import annotations

from enum import StrEnum

"""Task type enumeration for workflow routing."""


class TaskType(StrEnum):
    """Enumeration of recognized user intents."""

    GREETING = "GREETING"
    """User sent a social greeting with no task intent."""

    ITEM_LOOKUP = "ITEM_LOOKUP"
    """User is searching for a car."""

    DEALER_DETAILS = "DEALER_DETAILS"
    """User wants details about a dealer."""

    SCHEDULE_CALL = "SCHEDULE_CALL"
    """User wants to schedule a call with a dealer."""

    CONVERSATION = "CONVERSATION"
    """Contextual question about cars/dealers already seen this session."""

    UNKNOWN = "UNKNOWN"
    """Intent not recognized or insufficient confidence."""
