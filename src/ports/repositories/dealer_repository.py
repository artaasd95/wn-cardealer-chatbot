"""Dealer repository abstraction layer.

This module defines the DealerRepository protocol, which abstracts all dealer
lookup and search operations. It is the authoritative source for dealer data.

The application never constructs SQL, never opens a connection, and never
knows whether dealers come from a database, API, or cache. The repository
handles all query result formatting and validation.
"""

from __future__ import annotations

from typing import Protocol

from models.outputs.dealer import DealerRecord, DealerWithCars


class DealerRepository(Protocol):
    """Protocol for dealer search and retrieval.

    Implementations of this port are responsible for:
    - Retrieving dealer details by dealer_id
    - Loading a dealer and all their cars
    - Searching dealers by city or other attributes
    - Handling missing or incomplete dealer data gracefully

    Dealer data is always enriched from the authoritative catalog.
    The application never invents a dealer; it always asks the repository.
    """

    def get_by_id(self, dealer_id: str) -> DealerRecord | None:
        """Retrieve a dealer by ID.

        Args:
            dealer_id: The unique dealer identifier.

        Returns:
            The DealerRecord if found, None otherwise.
        """
        ...

    def get_with_cars(self, dealer_id: str) -> DealerWithCars | None:
        """Retrieve a dealer and all cars they are associated with.

        Args:
            dealer_id: The unique dealer identifier.

        Returns:
            A DealerWithCars containing dealer details and their car list,
            or None if the dealer does not exist.
        """
        ...

    def search_by_city(self, city: str) -> list[DealerRecord]:
        """Search for dealers in a given city.

        Args:
            city: The city name to search for.

        Returns:
            A list of dealers matching the city, or an empty list.
        """
        ...
