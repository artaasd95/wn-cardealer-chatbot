"""Dealer details workflow state machine.

Manages state transitions for the dealer details task:

    AWAITING_ACTION ──► DEALER_DETAILS_SHOWN  (dealer row loaded and validated)
    AWAITING_ACTION ──► AWAITING_ACTION        (no dealer to show — the guard
                                                asks the user to pick a car first)

DEALER_DETAILS_SHOWN (not COMPLETE) is the session state, so the turn can
still suggest its next tasks: schedule a call, or find another car. COMPLETE
stays reserved for the end of the conversation and is gated in the state
machine.
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
            return WorkflowState.DEALER_DETAILS_SHOWN

        return WorkflowState.AWAITING_ACTION
