"""Car repository abstraction layer.

This module defines the CarRepository protocol, which abstracts all car
lookup and search operations. It is the authoritative source for car data.

The application never constructs SQL, never opens a connection, and never
knows whether cars come from a database, API, or cache. The repository
handles all normalization, multi-match disambiguation, and query result
formatting.
"""

from __future__ import annotations

from typing import Protocol

from models.inputs.car import NormalizedCarQuery
from models.outputs.car import CarRecord, CarSearchResult


class CarRepository(Protocol):
    """Protocol for car search and retrieval.

    Implementations of this port are responsible for:
    - Normalizing car make/model/variant queries (case, aliases, abbreviations)
    - Searching the authoritative car catalog
    - Returning found / not_found / multiple results with candidates
    - Retrieving car details by ID
    - Honoring alias mappings to exercise normalization robustness

    Every car lookup request flows through the application layer, which
    calls LLMPort to extract make/model/variant, normalizes locally,
    then passes the normalized query to this repository.
    """

    def search(self, query: NormalizedCarQuery) -> CarSearchResult:
        """Search for cars matching the normalized query.

        Args:
            query: A NormalizedCarQuery with normalized make/model/variant fields.

        Returns:
            A CarSearchResult with status (found / not_found / multiple),
            cars (matching records), and candidates (for disambiguation).

            - found: Exactly one car matches. cars contains one record.
            - not_found: Zero cars match. cars is empty.
            - multiple: >1 cars match. cars contains all matches;
                       candidates contains a reduced list for disambiguation UI.
        """
        ...

    def get_by_id(self, car_id: str) -> CarRecord | None:
        """Retrieve a car by its ID.

        Args:
            car_id: The unique car identifier.

        Returns:
            The CarRecord if found, None otherwise.
        """
        ...

    def search_by_alias(self, alias: str) -> list[str]:
        """Look up normalized forms of an alias (make/model/variant abbreviation).

        Args:
            alias: An alias (e.g., "C-Class", "C Class", "BMW", "B.M.W.").

        Returns:
            A list of zero or more normalized forms this alias maps to,
            or an empty list if the alias is not recognized.
        """
        ...
