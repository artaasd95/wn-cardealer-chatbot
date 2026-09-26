"""Get dealer details use case.

Retrieves dealer information by ID from the repository.
"""

from __future__ import annotations

import logging

from application.tasks.dealer_details.workflow import DealerDetailsWorkflow
from domain.enums.workflow_state import WorkflowState
from domain.exceptions import DealerNotFoundError
from models.outputs.dealer import DealerRecord
from ports.repositories.dealer_repository import DealerRepository

logger = logging.getLogger(__name__)


class GetDealerDetailsUseCase:
    """Retrieve dealer details."""

    def __init__(self, dealer_repo: DealerRepository) -> None:
        """Initialize with dealer repository dependency.

        Args:
            dealer_repo: DealerRepository for dealer lookup.
        """
        self.dealer_repo = dealer_repo

    def execute(self, dealer_id: str) -> tuple[DealerRecord | None, WorkflowState]:
        """Retrieve dealer details.

        Args:
            dealer_id: The dealer identifier.

        Returns:
            Tuple of (dealer record or None, next workflow state).
        """
        try:
            dealer = self.dealer_repo.get_by_id(dealer_id)

            if not dealer:
                logger.warning(f"Dealer {dealer_id} not found")
                raise DealerNotFoundError(f"Dealer {dealer_id} not found")

            next_state = DealerDetailsWorkflow.advance(dealer_found=True)

            return dealer, next_state

        except DealerNotFoundError:
            raise

        except Exception as e:
            logger.error(f"Failed to retrieve dealer details: {str(e)}")
            raise DealerNotFoundError(f"Failed to retrieve dealer: {str(e)}") from e
