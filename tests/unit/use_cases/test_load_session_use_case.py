"""Tests for application/use_cases/load_session.py and save_session.py."""

from __future__ import annotations

import pytest

from application.use_cases.load_session import LoadSessionUseCase
from application.use_cases.save_session import SaveSessionUseCase
from domain.enums.workflow_state import WorkflowState
from DTO.inputs.session import SessionRequest
from models.outputs.session import SessionRecord
from ports.session_store import SessionStore

pytestmark = pytest.mark.unit


class TestLoadSessionUseCase:
    """Load: existing session, unknown id, empty id, expired session."""

    def test_loads_existing_session(self, session_store: SessionStore) -> None:
        """Happy path: an existing session id round-trips its state."""
        record = session_store.create(user_id="u-1")
        record.workflow_state = WorkflowState.AWAITING_ACTION.value
        session_store.save(record)

        snapshot = LoadSessionUseCase(session_store).execute(
            SessionRequest(session_id=record.session_id, user_id="u-1")
        )

        assert snapshot.session_id == record.session_id
        assert snapshot.workflow_state == WorkflowState.AWAITING_ACTION.value
        assert snapshot.user_id == "u-1"

    def test_unknown_session_id_creates_fresh_session(self, session_store: SessionStore) -> None:
        """Failure branch: an unknown id is never an error, a fresh one is made."""
        snapshot = LoadSessionUseCase(session_store).execute(
            SessionRequest(session_id="does-not-exist", user_id="u-1")
        )

        assert snapshot.session_id != "does-not-exist"
        assert snapshot.workflow_state == WorkflowState.START.value

    def test_empty_session_id_creates_fresh_session(self, session_store: SessionStore) -> None:
        """Failure branch: a first turn without any id gets a new session."""
        snapshot = LoadSessionUseCase(session_store).execute(
            SessionRequest(session_id="", user_id="u-2")
        )

        assert snapshot.session_id
        assert snapshot.user_id == "u-2"

    def test_expired_session_creates_fresh_session(self, session_store: SessionStore) -> None:
        """Failure branch: an expired in-memory session is replaced, not revived."""
        record = session_store.create(user_id="u-1", ttl_seconds=-1)

        snapshot = LoadSessionUseCase(session_store).execute(
            SessionRequest(session_id=record.session_id, user_id="u-1")
        )

        assert snapshot.session_id != record.session_id
        assert snapshot.workflow_state == WorkflowState.START.value


class TestSaveSessionUseCase:
    """Save: persisted record and persisted state change."""

    def test_persists_record(self, session_store: SessionStore) -> None:
        """Happy path: the saved record is readable back from the store."""
        record = session_store.create(user_id="u-1")
        record.workflow_state = WorkflowState.CAR_SELECTED.value
        record.selected_car_id = "C-0003"

        SaveSessionUseCase(session_store).execute(record)

        snapshot = session_store.get(record.session_id)
        assert snapshot is not None
        assert snapshot.workflow_state == WorkflowState.CAR_SELECTED.value
        assert snapshot.selected_car_id == "C-0003"

    def test_persists_updates_to_existing_session(self, session_store: SessionStore) -> None:
        """Happy path: later saves overwrite the earlier snapshot."""
        record = session_store.create(user_id="u-1")
        SaveSessionUseCase(session_store).execute(record)

        updated = SessionRecord.model_validate(record.model_dump())
        updated.workflow_state = WorkflowState.SCHEDULE_CONFIRMED.value
        SaveSessionUseCase(session_store).execute(updated)

        snapshot = session_store.get(record.session_id)
        assert snapshot is not None
        assert snapshot.workflow_state == WorkflowState.SCHEDULE_CONFIRMED.value
