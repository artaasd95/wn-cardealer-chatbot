"""SQLAlchemy table modules.

Importing this package registers every table on ``Base.metadata``, so
``Base.metadata.create_all`` creates the full schema — car, dealer, session,
message and schedule — no matter which table module the caller imported
directly.
"""

from __future__ import annotations

from infrastructure.database.tables.car import Car
from infrastructure.database.tables.dealer import Dealer
from infrastructure.database.tables.message import Message
from infrastructure.database.tables.schedule import Schedule
from infrastructure.database.tables.session import SessionTable

__all__ = ["Car", "Dealer", "Message", "Schedule", "SessionTable"]
