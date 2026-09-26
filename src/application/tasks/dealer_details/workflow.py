"""Dealer details workflow state machine.

Manages state transitions for the dealer details task.
"""

from __future__ import annotations

from domain.enums.workflow_state import WorkflowState


class DealerDetailsWorkflow:
    """State machine for dealer details retrieval."""

    @staticmethod
    def advance(dealer_found: bool) -> WorkflowState:
        """Advance workflow state based on dealer lookup result.

        Args:
            dealer_found: True if dealer was found, False otherwise.

        Returns:
            The next workflow state.
        """
        if dealer_found:
            return WorkflowState.COMPLETE

        return WorkflowState.AWAITING_ACTION
