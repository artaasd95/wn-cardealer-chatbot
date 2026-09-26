from __future__ import annotations

from enum import StrEnum

"""Workflow state enumeration for the conversation state machine."""


class WorkflowState(StrEnum):
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


# ---------------------------------------------------------------------------
# State machine — single source of truth for legal transitions.
# Both the domain entity (Session.advance_to) and the application layer
# (SessionService.advance_workflow) validate against this table, so a workflow
# step can only be advanced by application code and only along a legal edge.
#
# Shape of the graph:
#
#   START ─► AWAITING_CAR ─► CAR_SELECTED ─► AWAITING_ACTION
#               │                              │        │
#               └► CAR_NOT_FOUND               │        └► AWAITING_DATETIME ─► SCHEDULE_CONFIRMED
#                                              │                              │
#                                              └► DEALER_DETAILS_SHOWN ◄──────┘
#
# COMPLETE is the terminal state and is additionally gated: it may only be
# entered once a car and a dealer have been confirmed by a repository call.
# ---------------------------------------------------------------------------

_IDLE: frozenset[WorkflowState] = frozenset(
    {
        WorkflowState.START,
        WorkflowState.AWAITING_CAR,
        WorkflowState.CAR_SELECTED,
        WorkflowState.CAR_NOT_FOUND,
        WorkflowState.AWAITING_ACTION,
    }
)

_TASK_RESULTS: frozenset[WorkflowState] = frozenset(
    {
        WorkflowState.DEALER_DETAILS_SHOWN,
        WorkflowState.SCHEDULE_CONFIRMED,
        WorkflowState.AWAITING_DATETIME,
    }
)

LEGAL_TRANSITIONS: dict[WorkflowState, frozenset[WorkflowState]] = {
    WorkflowState.START: _IDLE,
    WorkflowState.AWAITING_CAR: _IDLE,
    WorkflowState.CAR_SELECTED: _IDLE,
    WorkflowState.CAR_NOT_FOUND: _IDLE,
    WorkflowState.AWAITING_ACTION: (
        _IDLE | _TASK_RESULTS | {WorkflowState.AWAITING_DEALER_DETAILS, WorkflowState.COMPLETE}
    ),
    WorkflowState.AWAITING_DEALER_DETAILS: frozenset(
        {
            WorkflowState.START,
            WorkflowState.AWAITING_CAR,
            WorkflowState.AWAITING_ACTION,
            WorkflowState.AWAITING_DEALER_DETAILS,
            WorkflowState.DEALER_DETAILS_SHOWN,
        }
    ),
    WorkflowState.DEALER_DETAILS_SHOWN: (
        _IDLE | _TASK_RESULTS | {WorkflowState.AWAITING_DEALER_DETAILS, WorkflowState.COMPLETE}
    ),
    WorkflowState.AWAITING_DATETIME: (_IDLE | _TASK_RESULTS | {WorkflowState.COMPLETE}),
    WorkflowState.SCHEDULE_CONFIRMED: (_IDLE | _TASK_RESULTS | {WorkflowState.COMPLETE}),
    WorkflowState.COMPLETE: (
        _IDLE | _TASK_RESULTS | {WorkflowState.COMPLETE, WorkflowState.AWAITING_DEALER_DETAILS}
    ),
}


def ensure_legal_transition(
    current: WorkflowState,
    target: WorkflowState,
    *,
    selected_car_id: str | None = None,
    selected_dealer_id: str | None = None,
) -> None:
    """Validate a workflow state transition.

    Args:
        current: The state the session is in now.
        target: The state the session wants to move to.
        selected_car_id: Car confirmed by a repository call, if any.
        selected_dealer_id: Dealer confirmed by a repository call, if any.

    Raises:
        InvalidTransitionError: If the edge is not defined in the state
            machine, or if COMPLETE is requested before a car and a dealer
            have both been confirmed.
    """
    from domain.exceptions import InvalidTransitionError

    allowed = LEGAL_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidTransitionError(
            from_state=current.value,
            to_state=target.value,
            reason="transition not defined in state machine",
        )

    if target is WorkflowState.COMPLETE and not (selected_car_id and selected_dealer_id):
        raise InvalidTransitionError(
            from_state=current.value,
            to_state=target.value,
            reason="COMPLETE requires a repository-confirmed car and dealer selection",
        )


def shortest_legal_path(
    current: WorkflowState,
    target: WorkflowState,
) -> list[WorkflowState] | None:
    """Find the shortest chain of legal edges from one state to another.

    The plan's state diagram shows intermediate states (CAR_SELECTED →
    AWAITING_ACTION, for example) that a single turn can pass through. This
    returns the full chain so the application can visit every state on it,
    validating each edge in turn.

    Args:
        current: The state to start from.
        target: The state to reach.

    Returns:
        [current, ..., target] following legal edges only, or None when no
        legal path exists.
    """
    if current is target:
        return [current]

    queue: list[list[WorkflowState]] = [[current]]
    seen: set[WorkflowState] = {current}

    while queue:
        path = queue.pop(0)
        for nxt in sorted(LEGAL_TRANSITIONS.get(path[-1], frozenset()), key=lambda s: s.value):
            if nxt in seen:
                continue
            candidate = [*path, nxt]
            if nxt is target:
                return candidate
            seen.add(nxt)
            queue.append(candidate)

    return None
