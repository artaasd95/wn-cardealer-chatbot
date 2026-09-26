"""Item lookup workflow state machine.

Manages state transitions for the car search task.
"""

from __future__ import annotations

from domain.enums.workflow_state import WorkflowState
from models.outputs.car import CarSearchResult


class ItemLookupWorkflow:
    """State machine for car item lookup."""

    @staticmethod
    def advance(result: CarSearchResult) -> WorkflowState:
        """Advance workflow state based on search result.

        Args:
            result: The car search result.

        Returns:
            The next workflow state.
        """
        if result.status == "found":
            return WorkflowState.CAR_SELECTED

        if result.status == "multiple":
            return WorkflowState.AWAITING_CAR  # Still awaiting user selection

        if result.status == "not_found":
            return WorkflowState.CAR_NOT_FOUND

        return WorkflowState.AWAITING_CAR
