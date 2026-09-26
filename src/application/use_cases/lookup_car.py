"""Lookup car use case.

Orchestrates the car search workflow: extract, normalize, search, select dealer.
"""

from __future__ import annotations

import logging

from application.tasks.item_lookup.workflow import ItemLookupWorkflow
from domain.enums.workflow_state import WorkflowState
from domain.exceptions import DealerNotFoundError
from DTO.inputs.car import CarSearchRequest
from infrastructure.llm.prompts.car_extraction import (
    build_car_extraction_prompt,
    normalize_make,
    normalize_model,
    normalize_variant,
)
from models.inputs.car import NormalizedCarQuery
from models.outputs.car import CarSearchResult
from models.outputs.dealer import DealerRecord
from ports.llm import LLMPort
from ports.repositories.car_repository import CarRepository
from ports.repositories.dealer_repository import DealerRepository

logger = logging.getLogger(__name__)


class LookupCarUseCase:
    """Execute car search workflow."""

    def __init__(
        self,
        llm: LLMPort,
        car_repo: CarRepository,
        dealer_repo: DealerRepository,
    ) -> None:
        """Initialize with dependencies.

        Args:
            llm: LLMPort for entity extraction.
            car_repo: CarRepository for car search.
            dealer_repo: DealerRepository for dealer lookup.
        """
        self.llm = llm
        self.car_repo = car_repo
        self.dealer_repo = dealer_repo

    def execute(
        self, user_message: str
    ) -> tuple[CarSearchResult, DealerRecord | None, WorkflowState]:
        """Execute car search.

        Args:
            user_message: The user's raw input.

        Returns:
            Tuple of (search result, selected dealer or None, next workflow state).
        """
        # Step 1: Extract car request via LLM
        prompt = build_car_extraction_prompt(user_message)
        extraction = self.llm.structured_completion(prompt, CarSearchRequest)

        # Step 2: Normalize
        query = NormalizedCarQuery(
            make=normalize_make(extraction.make),
            model=normalize_model(extraction.model),
            variant=normalize_variant(extraction.variant),
            year_from=extraction.year_from,
            year_to=extraction.year_to,
        )

        # Step 3: Search
        result = self.car_repo.search(query)

        # Step 4: If exactly one car found, load its dealer
        selected_dealer: DealerRecord | None = None
        if result.status == "found" and len(result.cars) == 1:
            car = result.cars[0]
            try:
                selected_dealer = self.dealer_repo.get_by_id(car.dealer_id)
                if not selected_dealer:
                    raise DealerNotFoundError(
                        f"Dealer {car.dealer_id} not found for car {car.car_id}"
                    )
            except Exception as e:
                logger.error(f"Failed to load dealer for car: {str(e)}")
                selected_dealer = None

        # Step 5: Determine next state
        next_state = ItemLookupWorkflow.advance(result)

        return result, selected_dealer, next_state
