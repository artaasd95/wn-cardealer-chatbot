"""Item lookup workflow state machine.

Manages state transitions for the car search task:

    AWAITING_CAR ──► CAR_SELECTED     (one car matched, dealer not loaded yet)
    AWAITING_CAR ──► AWAITING_ACTION  (one car matched and its dealer confirmed)
    AWAITING_CAR ──► CAR_NOT_FOUND     (no match)
    AWAITING_CAR ──► AWAITING_CAR      (multiple matches, waiting for the user
                                        to disambiguate)
"""

from __future__ import annotations

from domain.enums.workflow_state import WorkflowState
from models.outputs.car import CarSearchResult


class ItemLookupWorkflow:
    """State machine for car item lookup."""

    @staticmethod
    def advance(result: CarSearchResult, dealer_found: bool = False) -> WorkflowState:
        """Advance workflow state based on search result.

        Args:
            result: The car search result.
            dealer_found: True when the matched car's dealer was loaded from
                the repository in the same turn.

        Returns:
            The next workflow state.
        """
        if result.status == "found":
            # A confirmed dealer means the user can act immediately: the
            # diagram's CAR_SELECTED → AWAITING_ACTION step is taken in the
            # same turn, because both repository calls already succeeded.
            return WorkflowState.AWAITING_ACTION if dealer_found else WorkflowState.CAR_SELECTED

        if result.status == "multiple":
            return WorkflowState.AWAITING_CAR  # Still awaiting user selection

        if result.status == "not_found":
            return WorkflowState.CAR_NOT_FOUND

        return WorkflowState.AWAITING_CAR
