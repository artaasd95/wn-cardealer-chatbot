from __future__ import annotations

from dataclasses import dataclass

"""Dealer domain entity."""


@dataclass
class Dealer:
    """Domain entity representing a dealer."""

    dealer_id: str
    dealer_name: str
    city: str
    state: str | None
    address: str
    phone: str
    email: str
    rating: float | None = None

    def is_complete(self) -> bool:
        """Verify this dealer has all essential fields for contact.

        Returns:
            True if dealer_id, dealer_name, address, phone, and email are all present.
        """
        return bool(
            self.dealer_id and self.dealer_name and self.address and self.phone and self.email
        )

    def formatted_address(self) -> str:
        """Return a formatted full address.

        Returns:
            Address in the format: address, city, state (if present).
        """
        parts = [self.address, self.city]
        if self.state:
            parts.append(self.state)
        return ", ".join(parts)

    def display_name(self) -> str:
        """Return a display-friendly name with location.

        Returns:
            Format: "dealer_name (city, state)" or "dealer_name (city)" if no state.
        """
        location = f"{self.city}"
        if self.state:
            location += f", {self.state}"
        return f"{self.dealer_name} ({location})"
