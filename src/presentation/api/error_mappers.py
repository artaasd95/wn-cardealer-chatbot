"""Map domain exceptions to HTTP status codes and responses."""

from __future__ import annotations

from fastapi import HTTPException, status

from domain.exceptions import (
    CarNotFoundError,
    ConfigError,
    DealerNotFoundError,
    DomainError,
    InvalidScheduleError,
    InvalidTransitionError,
)


def domain_error_to_http(exc: DomainError) -> HTTPException:
    """Convert a domain exception to an HTTP exception.

    Args:
        exc: The domain exception.

    Returns:
        An HTTPException with appropriate status code.
    """
    if isinstance(exc, ConfigError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Configuration error: {str(exc)}",
        )

    if isinstance(exc, CarNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Car not found: {str(exc)}",
        )

    if isinstance(exc, DealerNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dealer not found: {str(exc)}",
        )

    if isinstance(exc, InvalidScheduleError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid schedule: {str(exc)}",
        )

    if isinstance(exc, InvalidTransitionError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid state transition: {str(exc)}",
        )

    # Generic domain error
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid request: {str(exc)}",
    )
