"""Dealer table definition."""

from __future__ import annotations

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.tables.base import Base


class Dealer(Base):
    """Dealer information table."""

    __tablename__ = "dealer"

    dealer_id: Mapped[str] = mapped_column(String, primary_key=True)
    dealer_name: Mapped[str] = mapped_column(String, index=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        """Return a readable representation."""
        return f"Dealer(dealer_id={self.dealer_id}, name={self.dealer_name}, city={self.city})"
