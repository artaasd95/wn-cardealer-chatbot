"""Dealer table definition."""

from __future__ import annotations

from sqlalchemy import Column, String

from infrastructure.database.tables.base import Base


class Dealer(Base):
    """Dealer information table."""

    __tablename__ = "dealer"

    dealer_id = Column(String, primary_key=True)
    dealer_name = Column(String, nullable=False, index=True)
    city = Column(String, nullable=True, index=True)
    state = Column(String, nullable=True)
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    rating = Column(String, nullable=True)

    def __repr__(self) -> str:
        """Return a readable representation."""
        return f"Dealer(dealer_id={self.dealer_id}, name={self.dealer_name}, city={self.city})"
