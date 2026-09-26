from __future__ import annotations

from pydantic import BaseModel, Field

"""Internal models for dealer lookup."""


class DealerQuery(BaseModel):
    """Dealer lookup key."""

    dealer_id: str | None = Field(
        None,
        description="Dealer ID for direct lookup.",
    )
    city: str | None = Field(
        None,
        description="Optional city filter.",
    )
