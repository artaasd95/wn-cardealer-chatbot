from __future__ import annotations

import pytest
from datetime import datetime
from pydantic import ValidationError

from DTO.outputs.chat import ChatResponse, ClarificationMessage
from DTO.outputs.car import CarSummary, CarCandidateList
from DTO.outputs.dealer import DealerDetails, CarReference
from DTO.outputs.schedule import ScheduleConfirmation
from DTO.outputs.session import SessionSnapshot


class TestChatResponse:
    """Tests for ChatResponse DTO."""

    def test_valid_response(self):
        """Test creating a valid ChatResponse."""
        resp = ChatResponse(
            session_id="sess_123",
            reply="I found a BMW 3-Series for you.",
            workflow_state="CAR_SELECTED",
            suggested_actions=["Get dealer details", "Schedule a call"],
            requires_input=True,
        )
        assert resp.session_id == "sess_123"
        assert resp.reply == "I found a BMW 3-Series for you."
        assert resp.workflow_state == "CAR_SELECTED"
        assert len(resp.suggested_actions) == 2
        assert resp.requires_input is True

    def test_default_suggested_actions(self):
        """Test that suggested_actions defaults to empty list."""
        resp = ChatResponse(
            session_id="sess_123",
            reply="Hello",
            workflow_state="AWAITING_CAR",
        )
        assert resp.suggested_actions == []

    def test_default_requires_input(self):
        """Test that requires_input defaults to True."""
        resp = ChatResponse(
            session_id="sess_123",
            reply="Hello",
            workflow_state="AWAITING_CAR",
        )
        assert resp.requires_input is True

    def test_missing_required_field_fails(self):
        """Test that missing required fields fail."""
        with pytest.raises(ValidationError):
            ChatResponse(session_id="sess_123")  # missing reply


class TestClarificationMessage:
    """Tests for ClarificationMessage DTO."""

    def test_valid_clarification(self):
        """Test creating a valid ClarificationMessage."""
        msg = ClarificationMessage(
            reply="Which BMW model are you interested in?",
            missing_fields=["model"],
            options=["3-Series", "5-Series", "7-Series"],
        )
        assert msg.reply == "Which BMW model are you interested in?"
        assert msg.missing_fields == ["model"]
        assert msg.options == ["3-Series", "5-Series", "7-Series"]

    def test_default_missing_fields(self):
        """Test that missing_fields defaults to empty list."""
        msg = ClarificationMessage(reply="Which model?")
        assert msg.missing_fields == []

    def test_options_none_allowed(self):
        """Test that options can be None."""
        msg = ClarificationMessage(
            reply="Please clarify",
            options=None,
        )
        assert msg.options is None


class TestCarSummary:
    """Tests for CarSummary DTO."""

    def test_valid_car_summary(self):
        """Test creating a valid CarSummary."""
        car = CarSummary(
            car_id="C-001",
            make="BMW",
            model="3-Series",
            variant="xDrive",
            year=2023,
            price_range="$35,000 - $45,000",
        )
        assert car.car_id == "C-001"
        assert car.make == "BMW"
        assert car.model == "3-Series"
        assert car.variant == "xDrive"
        assert car.year == 2023
        assert car.price_range == "$35,000 - $45,000"

    def test_variant_optional(self):
        """Test that variant is optional."""
        car = CarSummary(
            car_id="C-001",
            make="BMW",
            model="3-Series",
            year=2023,
            price_range="$35,000 - $45,000",
        )
        assert car.variant is None

    def test_year_bounds(self):
        """Test year bounds validation."""
        # Valid
        car = CarSummary(
            car_id="C-001",
            make="BMW",
            model="3-Series",
            year=1900,
            price_range="$0 - $100",
        )
        assert car.year == 1900

        # Invalid: too low
        with pytest.raises(ValidationError):
            CarSummary(
                car_id="C-001",
                make="BMW",
                model="3-Series",
                year=1899,
                price_range="$0 - $100",
            )


class TestCarCandidateList:
    """Tests for CarCandidateList DTO."""

    def test_valid_candidate_list(self):
        """Test creating a valid CarCandidateList."""
        candidates = [
            CarSummary(
                car_id="C-001",
                make="BMW",
                model="3-Series",
                year=2023,
                price_range="$35,000 - $45,000",
            ),
            CarSummary(
                car_id="C-002",
                make="BMW",
                model="3-Series",
                year=2024,
                price_range="$40,000 - $50,000",
            ),
        ]
        cand_list = CarCandidateList(
            candidates=candidates,
            message="Which 3-Series are you interested in?",
        )
        assert len(cand_list.candidates) == 2
        assert cand_list.message == "Which 3-Series are you interested in?"


class TestCarReference:
    """Tests for CarReference (used in DealerDetails)."""

    def test_valid_car_reference(self):
        """Test creating a valid CarReference."""
        ref = CarReference(
            car_id="C-001",
            make="BMW",
            model="3-Series",
            year=2023,
        )
        assert ref.car_id == "C-001"
        assert ref.make == "BMW"
        assert ref.model == "3-Series"
        assert ref.year == 2023


class TestDealerDetails:
    """Tests for DealerDetails DTO."""

    def test_valid_dealer_details(self):
        """Test creating valid DealerDetails."""
        dealer = DealerDetails(
            dealer_id="D-001",
            name="Downtown BMW",
            city="New York",
            address="123 Main St, New York, NY 10001",
            phone="+1-555-0100",
            email="sales@downtownbmw.com",
            rating=4.7,
            cars=[],
        )
        assert dealer.dealer_id == "D-001"
        assert dealer.name == "Downtown BMW"
        assert dealer.city == "New York"
        assert dealer.phone == "+1-555-0100"
        assert dealer.email == "sales@downtownbmw.com"
        assert dealer.rating == 4.7

    def test_rating_bounds(self):
        """Test rating bounds validation."""
        # Valid: 0
        dealer = DealerDetails(
            dealer_id="D-001",
            name="Test",
            city="City",
            address="Address",
            phone="111-1111",
            email="test@test.com",
            rating=0.0,
        )
        assert dealer.rating == 0.0

        # Valid: 5
        dealer = DealerDetails(
            dealer_id="D-001",
            name="Test",
            city="City",
            address="Address",
            phone="111-1111",
            email="test@test.com",
            rating=5.0,
        )
        assert dealer.rating == 5.0

        # Invalid: > 5
        with pytest.raises(ValidationError):
            DealerDetails(
                dealer_id="D-001",
                name="Test",
                city="City",
                address="Address",
                phone="111-1111",
                email="test@test.com",
                rating=5.1,
            )

    def test_rating_optional(self):
        """Test that rating is optional."""
        dealer = DealerDetails(
            dealer_id="D-001",
            name="Test",
            city="City",
            address="Address",
            phone="111-1111",
            email="test@test.com",
        )
        assert dealer.rating is None

    def test_cars_default_empty(self):
        """Test that cars defaults to empty list."""
        dealer = DealerDetails(
            dealer_id="D-001",
            name="Test",
            city="City",
            address="Address",
            phone="111-1111",
            email="test@test.com",
        )
        assert dealer.cars == []


class TestScheduleConfirmation:
    """Tests for ScheduleConfirmation DTO."""

    def test_valid_confirmation(self):
        """Test creating a valid ScheduleConfirmation."""
        scheduled_time = datetime(2024, 12, 26, 15, 0, 0)
        confirm = ScheduleConfirmation(
            dealer_id="D-001",
            car_id="C-001",
            scheduled_for=scheduled_time,
            timezone="America/New_York",
            status="confirmed",
        )
        assert confirm.dealer_id == "D-001"
        assert confirm.car_id == "C-001"
        assert confirm.scheduled_for == scheduled_time
        assert confirm.timezone == "America/New_York"
        assert confirm.status == "confirmed"

    def test_default_status(self):
        """Test that status defaults to 'confirmed'."""
        scheduled_time = datetime(2024, 12, 26, 15, 0, 0)
        confirm = ScheduleConfirmation(
            dealer_id="D-001",
            car_id="C-001",
            scheduled_for=scheduled_time,
            timezone="UTC",
        )
        assert confirm.status == "confirmed"


class TestSessionSnapshot:
    """Tests for SessionSnapshot DTO."""

    def test_valid_snapshot(self):
        """Test creating a valid SessionSnapshot."""
        snap = SessionSnapshot(
            session_id="sess_123",
            workflow_state="CAR_SELECTED",
            selected_car="C-001",
            selected_dealer="D-001",
            history_length=5,
        )
        assert snap.session_id == "sess_123"
        assert snap.workflow_state == "CAR_SELECTED"
        assert snap.selected_car == "C-001"
        assert snap.selected_dealer == "D-001"
        assert snap.history_length == 5

    def test_selected_car_optional(self):
        """Test that selected_car is optional."""
        snap = SessionSnapshot(
            session_id="sess_123",
            workflow_state="AWAITING_CAR",
        )
        assert snap.selected_car is None
        assert snap.selected_dealer is None

    def test_history_length_default(self):
        """Test that history_length defaults to 0."""
        snap = SessionSnapshot(
            session_id="sess_123",
            workflow_state="START",
        )
        assert snap.history_length == 0
