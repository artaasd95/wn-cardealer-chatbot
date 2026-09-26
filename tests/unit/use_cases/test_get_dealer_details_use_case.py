"""Tests for application/use_cases/get_dealer_details.py."""

from __future__ import annotations

import pytest

from application.use_cases.get_dealer_details import GetDealerDetailsUseCase
from domain.enums.workflow_state import WorkflowState
from domain.exceptions import DealerNotFoundError
from tests.fakes import StubDealerRepository, make_dealer

pytestmark = pytest.mark.unit


class TestGetDealerDetailsUseCase:
    """Steps 1-6 of the dealer-details flow."""

    def test_found_returns_record_and_state(self) -> None:
        """Happy path: the dealer row comes back with the shown state."""
        dealer = make_dealer("D-003")
        repo = StubDealerRepository(by_id={"D-003": dealer})

        record, next_state = GetDealerDetailsUseCase(repo).execute("D-003")

        assert record == dealer
        assert next_state is WorkflowState.DEALER_DETAILS_SHOWN

    def test_incomplete_row_still_returns_partial_details(self) -> None:
        """Edge case: a row with empty fields is partial, not a crash."""
        dealer = make_dealer("D-012", name="Apex AutoCare", email="", rating=4.1)
        repo = StubDealerRepository(by_id={"D-012": dealer})

        record, next_state = GetDealerDetailsUseCase(repo).execute("D-012")

        assert record is not None
        assert record.email == ""
        assert record.dealer_name == "Apex AutoCare"
        assert next_state is WorkflowState.DEALER_DETAILS_SHOWN

    def test_missing_dealer_raises(self) -> None:
        """Failure branch: an unknown dealer id is a domain error."""
        with pytest.raises(DealerNotFoundError, match="Dealer not found: D-999"):
            GetDealerDetailsUseCase(StubDealerRepository()).execute("D-999")

    def test_repository_failure_is_wrapped(self) -> None:
        """Failure branch: infrastructure trouble maps to a domain error."""
        repo = StubDealerRepository(error=RuntimeError("connection reset"))

        with pytest.raises(DealerNotFoundError, match="Failed to retrieve dealer"):
            GetDealerDetailsUseCase(repo).execute("D-003")
