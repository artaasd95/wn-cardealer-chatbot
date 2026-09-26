from __future__ import annotations

from pydantic import BaseModel, Field

"""Data Transfer Objects for dealer details request boundary."""


class DealerDetailsRequest(BaseModel):
    """Request for dealer details."""

    dealer_id: str = Field(
        ...,
        description="Dealer ID to fetch details for.",
    )
    car_id: str = Field(
        ...,
        description="Associated car ID for context.",
    )
