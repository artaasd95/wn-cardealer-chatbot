from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from domain.entities import Car, Dealer, Message, Schedule, Session
from domain.enums import TaskType, WorkflowState
from domain.exceptions import (
    InvalidScheduleError,
    InvalidTransitionError,
)
from models.inputs.car import CarExtraction, NormalizedCarQuery


class TestTaskType:
    """Tests for TaskType enum."""

    def test_all_values(self):
        """Test all TaskType enum values exist."""
        assert TaskType.ITEM_LOOKUP.value == "ITEM_LOOKUP"
        assert TaskType.DEALER_DETAILS.value == "DEALER_DETAILS"
        assert TaskType.SCHEDULE_CALL.value == "SCHEDULE_CALL"
        assert TaskType.UNKNOWN.value == "UNKNOWN"

    def test_string_comparison(self):
        """Test TaskType can be compared as string."""
        assert TaskType.ITEM_LOOKUP == "ITEM_LOOKUP"
        assert TaskType.DEALER_DETAILS.value == "DEALER_DETAILS"


class TestWorkflowState:
    """Tests for WorkflowState enum."""

    def test_all_states(self):
        """Test all WorkflowState enum values exist."""
        states = [
            WorkflowState.START,
            WorkflowState.AWAITING_CAR,
            WorkflowState.CAR_SELECTED,
            WorkflowState.CAR_NOT_FOUND,
            WorkflowState.AWAITING_ACTION,
            WorkflowState.AWAITING_DEALER_DETAILS,
            WorkflowState.DEALER_DETAILS_SHOWN,
            WorkflowState.AWAITING_DATETIME,
            WorkflowState.SCHEDULE_CONFIRMED,
            WorkflowState.COMPLETE,
        ]
        assert len(states) == 10

    def test_string_conversion(self):
        """Test WorkflowState converts to string properly."""
        assert str(WorkflowState.START) == "START"
        assert str(WorkflowState.COMPLETE) == "COMPLETE"


class TestCarNormalization:
    """Tests for Car entity normalization."""

    def test_normalize_full_extraction(self):
        """Test normalizing a complete car extraction."""
        extraction = CarExtraction(
            make="BMW",
            model="3-Series",
            variant="xDrive",
            year_from=2020,
            year_to=2024,
        )
        normalized = Car.normalize_extraction(extraction)
        assert normalized.make == "Bmw"
        assert normalized.model == "3-Series"
        assert normalized.variant == "Xdrive"
        assert normalized.year_from == 2020
        assert normalized.year_to == 2024

    def test_normalize_partial_extraction(self):
        """Test normalizing a partial extraction."""
        extraction = CarExtraction(make="BMW")
        normalized = Car.normalize_extraction(extraction)
        assert normalized.make == "Bmw"
        assert normalized.model is None
        assert normalized.variant is None

    def test_normalize_swaps_year_bounds(self):
        """Test that year_from > year_to gets swapped."""
        extraction = CarExtraction(year_from=2024, year_to=2020)
        normalized = Car.normalize_extraction(extraction)
        assert normalized.year_from == 2020
        assert normalized.year_to == 2024

    def test_normalize_whitespace(self):
        """Test that whitespace is stripped."""
        extraction = CarExtraction(make="  BMW  ", model="  3-Series  ")
        normalized = Car.normalize_extraction(extraction)
        assert normalized.make == "Bmw"
        assert normalized.model == "3-Series"


class TestCarMatching:
    """Tests for Car.matches() query logic."""

    def test_exact_make_match(self):
        """Test matching by make only."""
        car = Car(
            car_id="C-001",
            make="BMW",
            model="3-Series",
            variant=None,
            year=2023,
            fuel_type=None,
            transmission=None,
            body_type=None,
            price_min=None,
            price_max=None,
            mileage_km=None,
            features=None,
            dealer_id="D-001",
        )
        query = NormalizedCarQuery(make="bmw")
        assert car.matches(query)

    def test_make_mismatch(self):
        """Test that non-matching make returns False."""
        car = Car(
            car_id="C-001",
            make="BMW",
            model="3-Series",
            variant=None,
            year=2023,
            fuel_type=None,
            transmission=None,
            body_type=None,
            price_min=None,
            price_max=None,
            mileage_km=None,
            features=None,
            dealer_id="D-001",
        )
        query = NormalizedCarQuery(make="Mercedes")
        assert not car.matches(query)

    def test_year_range_match(self):
        """Test matching within year range."""
        car = Car(
            car_id="C-001",
            make="BMW",
            model="3-Series",
            variant=None,
            year=2022,
            fuel_type=None,
            transmission=None,
            body_type=None,
            price_min=None,
            price_max=None,
            mileage_km=None,
            features=None,
            dealer_id="D-001",
        )
        query = NormalizedCarQuery(year_from=2020, year_to=2024)
        assert car.matches(query)

    def test_year_too_old(self):
        """Test that year below range returns False."""
        car = Car(
            car_id="C-001",
            make="BMW",
            model="3-Series",
            variant=None,
            year=2019,
            fuel_type=None,
            transmission=None,
            body_type=None,
            price_min=None,
            price_max=None,
            mileage_km=None,
            features=None,
            dealer_id="D-001",
        )
        query = NormalizedCarQuery(year_from=2020)
        assert not car.matches(query)


class TestDealerValidation:
    """Tests for Dealer entity validation."""

    def test_complete_dealer(self):
        """Test a complete dealer passes validation."""
        dealer = Dealer(
            dealer_id="D-001",
            dealer_name="Downtown BMW",
            city="New York",
            state="NY",
            address="123 Main St",
            phone="+1-555-0100",
            email="sales@downtownbmw.com",
        )
        assert dealer.is_complete()

    def test_incomplete_dealer_missing_email(self):
        """Test that missing email fails validation."""
        dealer = Dealer(
            dealer_id="D-001",
            dealer_name="Downtown BMW",
            city="New York",
            state="NY",
            address="123 Main St",
            phone="+1-555-0100",
            email="",
        )
        assert not dealer.is_complete()

    def test_formatted_address(self):
        """Test address formatting."""
        dealer = Dealer(
            dealer_id="D-001",
            dealer_name="Downtown BMW",
            city="New York",
            state="NY",
            address="123 Main St",
            phone="+1-555-0100",
            email="sales@downtownbmw.com",
        )
        assert dealer.formatted_address() == "123 Main St, New York, NY"

    def test_display_name(self):
        """Test display name formatting."""
        dealer = Dealer(
            dealer_id="D-001",
            dealer_name="Downtown BMW",
            city="New York",
            state="NY",
            address="123 Main St",
            phone="+1-555-0100",
            email="sales@downtownbmw.com",
        )
        assert dealer.display_name() == "Downtown BMW (New York, NY)"


class TestScheduleValidation:
    """Tests for Schedule entity validation."""

    def test_valid_future_schedule(self):
        """Test a valid future schedule passes validation."""
        future_time = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
        schedule = Schedule(
            schedule_id="sched_123",
            dealer_id="D-001",
            car_id="C-001",
            scheduled_for=future_time,
            timezone="America/New_York",
        )
        schedule.validate()  # Should not raise

    def test_past_date_rejected(self):
        """Test that past dates are rejected."""
        past_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
        schedule = Schedule(
            schedule_id="sched_123",
            dealer_id="D-001",
            car_id="C-001",
            scheduled_for=past_time,
            timezone="America/New_York",
        )
        with pytest.raises(InvalidScheduleError):
            schedule.validate()

    def test_empty_timezone_rejected(self):
        """Test that empty timezone is rejected."""
        future_time = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
        schedule = Schedule(
            schedule_id="sched_123",
            dealer_id="D-001",
            car_id="C-001",
            scheduled_for=future_time,
            timezone="",
        )
        with pytest.raises(InvalidScheduleError):
            schedule.validate()

    def test_invalid_status_rejected(self):
        """Test that invalid status is rejected."""
        future_time = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
        schedule = Schedule(
            schedule_id="sched_123",
            dealer_id="D-001",
            car_id="C-001",
            scheduled_for=future_time,
            timezone="UTC",
            status="invalid_status",
        )
        with pytest.raises(InvalidScheduleError):
            schedule.validate()

    def test_is_future(self):
        """Test is_future() method."""
        future_time = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
        schedule = Schedule(
            schedule_id="sched_123",
            dealer_id="D-001",
            car_id="C-001",
            scheduled_for=future_time,
            timezone="UTC",
        )
        assert schedule.is_future()

    def test_time_until_scheduled(self):
        """Test time_until_scheduled() returns positive seconds."""
        future_time = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=2)
        schedule = Schedule(
            schedule_id="sched_123",
            dealer_id="D-001",
            car_id="C-001",
            scheduled_for=future_time,
            timezone="UTC",
        )
        seconds = schedule.time_until_scheduled()
        assert 7000 < seconds < 7300  # ~2 hours


class TestMessage:
    """Tests for Message entity."""

    def test_user_message(self):
        """Test creating a user message."""
        msg = Message(role="user", content="I'm looking for a BMW")
        assert msg.is_user_message()
        assert not msg.is_assistant_message()
        assert msg.length() == 21

    def test_assistant_message(self):
        """Test creating an assistant message."""
        msg = Message(role="assistant", content="Found 3 BMWs")
        assert not msg.is_user_message()
        assert msg.is_assistant_message()

    def test_default_timestamp(self):
        """Test that created_at defaults to now."""
        msg = Message(role="user", content="Hello")
        assert isinstance(msg.created_at, datetime)


class TestSessionStateMachine:
    """Tests for Session entity state machine."""

    def test_legal_transition_start_to_awaiting_car(self):
        """Test START -> AWAITING_CAR is legal."""
        session = Session(
            session_id="sess_123",
            user_id="user_456",
            workflow_state=WorkflowState.START,
        )
        session.advance_to(WorkflowState.AWAITING_CAR)
        assert session.workflow_state == WorkflowState.AWAITING_CAR

    def test_illegal_transition_start_to_complete(self):
        """Test START -> COMPLETE is illegal."""
        session = Session(
            session_id="sess_123",
            user_id="user_456",
            workflow_state=WorkflowState.START,
        )
        with pytest.raises(InvalidTransitionError):
            session.advance_to(WorkflowState.COMPLETE)

    def test_illegal_transition_awaiting_car_to_dealer_details(self):
        """Test AWAITING_CAR -> DEALER_DETAILS_SHOWN is illegal."""
        session = Session(
            session_id="sess_123",
            user_id="user_456",
            workflow_state=WorkflowState.AWAITING_CAR,
        )
        with pytest.raises(InvalidTransitionError):
            session.advance_to(WorkflowState.DEALER_DETAILS_SHOWN)

    def test_full_flow_car_selected(self):
        """Test full flow: START -> AWAITING_CAR -> CAR_SELECTED."""
        session = Session(
            session_id="sess_123",
            user_id="user_456",
            workflow_state=WorkflowState.START,
        )
        session.advance_to(WorkflowState.AWAITING_CAR)
        session.advance_to(WorkflowState.CAR_SELECTED)
        assert session.workflow_state == WorkflowState.CAR_SELECTED

    def test_reset_clears_selections(self):
        """Test reset_to_start() clears selections."""
        session = Session(
            session_id="sess_123",
            user_id="user_456",
            workflow_state=WorkflowState.CAR_SELECTED,
            selected_car_id="C-001",
            selected_dealer_id="D-001",
        )
        session.reset_to_start()
        assert session.workflow_state == WorkflowState.START
        assert session.selected_car_id is None
        assert session.selected_dealer_id is None

    def test_add_message_updates_history(self):
        """Test add_message() appends to history."""
        session = Session(
            session_id="sess_123",
            user_id="user_456",
            workflow_state=WorkflowState.START,
        )
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there")
        assert len(session.conversation_history) == 2

    def test_last_user_message(self):
        """Test last_user_message() retrieves the most recent user message."""
        session = Session(
            session_id="sess_123",
            user_id="user_456",
            workflow_state=WorkflowState.START,
        )
        session.add_message("user", "First message")
        session.add_message("assistant", "Response")
        session.add_message("user", "Second message")
        assert session.last_user_message() == "Second message"

    def test_last_assistant_message(self):
        """Test last_assistant_message() retrieves the most recent assistant message."""
        session = Session(
            session_id="sess_123",
            user_id="user_456",
            workflow_state=WorkflowState.START,
        )
        session.add_message("user", "Hello")
        session.add_message("assistant", "First response")
        session.add_message("user", "Second message")
        session.add_message("assistant", "Second response")
        assert session.last_assistant_message() == "Second response"

    def test_is_expired_false_when_no_expiry(self):
        """Test is_expired() returns False when expires_at is None."""
        session = Session(
            session_id="sess_123",
            user_id="user_456",
            workflow_state=WorkflowState.START,
            expires_at=None,
        )
        assert not session.is_expired()

    def test_is_expired_true_for_past_time(self):
        """Test is_expired() returns True for past expires_at."""
        session = Session(
            session_id="sess_123",
            user_id="user_456",
            workflow_state=WorkflowState.START,
            expires_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1),
        )
        assert session.is_expired()

    def test_is_complete_true_in_complete_state(self):
        """Test is_complete() returns True for COMPLETE state."""
        session = Session(
            session_id="sess_123",
            user_id="user_456",
            workflow_state=WorkflowState.COMPLETE,
        )
        assert session.is_complete()

    def test_is_complete_false_in_other_states(self):
        """Test is_complete() returns False for non-COMPLETE states."""
        session = Session(
            session_id="sess_123",
            user_id="user_456",
            workflow_state=WorkflowState.START,
        )
        assert not session.is_complete()
