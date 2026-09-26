from __future__ import annotations

"""Domain layer exceptions."""


class DomainError(Exception):
    """Base exception for all domain-layer errors."""

    pass


class CarNotFoundError(DomainError):
    """Raised when a car search yields no results."""

    def __init__(self, query: str | None = None) -> None:
        """Initialize with optional query details."""
        msg = "No cars found"
        if query:
            msg += f": {query}"
        super().__init__(msg)


class DealerNotFoundError(DomainError):
    """Raised when a dealer lookup fails."""

    def __init__(self, dealer_id: str | None = None) -> None:
        """Initialize with optional dealer ID."""
        msg = "Dealer not found"
        if dealer_id:
            msg += f": {dealer_id}"
        super().__init__(msg)


class InvalidTransitionError(DomainError):
    """Raised when a workflow state transition is illegal."""

    def __init__(self, from_state: str, to_state: str, reason: str | None = None) -> None:
        """Initialize with state transition details."""
        msg = f"Invalid transition: {from_state} → {to_state}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


class InvalidScheduleError(DomainError):
    """Raised when a schedule request is invalid."""

    def __init__(self, reason: str) -> None:
        """Initialize with the reason."""
        super().__init__(f"Invalid schedule: {reason}")


class ConfigError(DomainError):
    """Raised when configuration is invalid."""

    def __init__(self, key: str, reason: str | None = None) -> None:
        """Initialize with a config key and an optional reason.

        Args:
            key: The configuration key at fault, or a complete message when
                ``reason`` is omitted.
            reason: Why the configuration was rejected.
        """
        if reason is None:
            super().__init__(f"Config error: {key}")
        else:
            super().__init__(f"Config error for {key}: {reason}")
