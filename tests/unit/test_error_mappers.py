"""Tests for presentation/api/error_mappers.py."""

from __future__ import annotations

from fastapi import status

from domain.exceptions import (
    CarNotFoundError,
    ConfigError,
    DealerNotFoundError,
    DomainError,
    InvalidScheduleError,
    InvalidTransitionError,
)
from presentation.api.error_mappers import domain_error_to_http


class TestErrorMappers:
    """Tests for domain exception to HTTP error mapping."""

    def test_config_error_maps_to_500(self) -> None:
        """Test that ConfigError maps to 500 Internal Server Error."""
        exc = ConfigError("llm_api_key", "API key not configured")
        http_exc = domain_error_to_http(exc)

        assert http_exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Configuration error" in http_exc.detail

    def test_car_not_found_error_maps_to_404(self) -> None:
        """Test that CarNotFoundError maps to 404 Not Found."""
        exc = CarNotFoundError("No cars match the search")
        http_exc = domain_error_to_http(exc)

        assert http_exc.status_code == status.HTTP_404_NOT_FOUND
        assert "Car not found" in http_exc.detail

    def test_dealer_not_found_error_maps_to_404(self) -> None:
        """Test that DealerNotFoundError maps to 404 Not Found."""
        exc = DealerNotFoundError("Dealer D-123 not found")
        http_exc = domain_error_to_http(exc)

        assert http_exc.status_code == status.HTTP_404_NOT_FOUND
        assert "Dealer not found" in http_exc.detail

    def test_invalid_schedule_error_maps_to_400(self) -> None:
        """Test that InvalidScheduleError maps to 400 Bad Request."""
        exc = InvalidScheduleError("Date must be in the future")
        http_exc = domain_error_to_http(exc)

        assert http_exc.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid schedule" in http_exc.detail

    def test_invalid_transition_error_maps_to_409(self) -> None:
        """Test that InvalidTransitionError maps to 409 Conflict."""
        exc = InvalidTransitionError("START", "COMPLETE", "Invalid transition")
        http_exc = domain_error_to_http(exc)

        assert http_exc.status_code == status.HTTP_409_CONFLICT
        assert "Invalid state transition" in http_exc.detail

    def test_generic_domain_error_maps_to_400(self) -> None:
        """Test that generic DomainError maps to 400 Bad Request."""
        exc = DomainError("Something went wrong")
        http_exc = domain_error_to_http(exc)

        assert http_exc.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid request" in http_exc.detail
