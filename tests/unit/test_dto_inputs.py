from __future__ import annotations

import pytest
from pydantic import ValidationError

from DTO.inputs.car import CarSearchRequest
from DTO.inputs.chat import ChatRequest
from DTO.inputs.dealer import DealerDetailsRequest
from DTO.inputs.schedule import ScheduleCallRequest
from DTO.inputs.session import CreateSessionRequest, SessionRequest


class TestChatRequest:
    """Tests for ChatRequest DTO."""

    def test_valid_with_all_fields(self):
        """Test creating a valid ChatRequest with all fields."""
        req = ChatRequest(
            session_id="sess_123",
            message="Hello, I'm looking for a BMW",
            user_id="user_456",
        )
        assert req.session_id == "sess_123"
        assert req.message == "Hello, I'm looking for a BMW"
        assert req.user_id == "user_456"

    def test_valid_with_required_only(self):
        """Test creating a ChatRequest with only required field."""
        req = ChatRequest(message="Hello")
        assert req.session_id is None
        assert req.message == "Hello"
        assert req.user_id is None

    def test_message_empty_fails(self):
        """Test that empty message is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(message="")
        assert "String should have at least 1 character" in str(exc_info.value)

    def test_message_too_long_fails(self):
        """Test that message exceeding max length is rejected."""
        long_msg = "x" * 2001
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(message=long_msg)
        assert "String should have at most 2000 characters" in str(exc_info.value)

    def test_message_at_max_length_passes(self):
        """Test that message at exactly max length passes."""
        msg = "x" * 2000
        req = ChatRequest(message=msg)
        assert req.message == msg

    def test_none_session_id_allowed(self):
        """Test that None session_id is allowed (creates new session)."""
        req = ChatRequest(session_id=None, message="test")
        assert req.session_id is None


class TestCarSearchRequest:
    """Tests for CarSearchRequest DTO."""

    def test_valid_full_query(self):
        """Test valid car search with all fields."""
        req = CarSearchRequest(
            make="BMW",
            model="3-Series",
            variant="xDrive",
            year_from=2020,
            year_to=2024,
        )
        assert req.make == "BMW"
        assert req.model == "3-Series"
        assert req.variant == "xDrive"
        assert req.year_from == 2020
        assert req.year_to == 2024

    def test_valid_partial_query(self):
        """Test valid car search with only make."""
        req = CarSearchRequest(make="BMW")
        assert req.make == "BMW"
        assert req.model is None
        assert req.variant is None
        assert req.year_from is None
        assert req.year_to is None

    def test_all_fields_optional(self):
        """Test that all fields are optional."""
        req = CarSearchRequest()
        assert req.make is None
        assert req.model is None
        assert req.variant is None
        assert req.year_from is None
        assert req.year_to is None

    def test_year_from_validation(self):
        """Test year_from bounds validation."""
        # Valid
        req = CarSearchRequest(year_from=1900)
        assert req.year_from == 1900

        # Invalid: too low
        with pytest.raises(ValidationError) as exc_info:
            CarSearchRequest(year_from=1899)
        assert "greater than or equal to 1900" in str(exc_info.value)

    def test_year_to_validation(self):
        """Test year_to bounds validation."""
        # Valid
        req = CarSearchRequest(year_to=2100)
        assert req.year_to == 2100

        # Invalid: too high
        with pytest.raises(ValidationError) as exc_info:
            CarSearchRequest(year_to=2101)
        assert "less than or equal to 2100" in str(exc_info.value)


class TestDealerDetailsRequest:
    """Tests for DealerDetailsRequest DTO."""

    def test_valid_request(self):
        """Test valid dealer details request."""
        req = DealerDetailsRequest(dealer_id="D-001", car_id="C-001")
        assert req.dealer_id == "D-001"
        assert req.car_id == "C-001"

    def test_missing_dealer_id_fails(self):
        """Test that missing dealer_id fails."""
        with pytest.raises(ValidationError):
            DealerDetailsRequest(car_id="C-001")

    def test_missing_car_id_fails(self):
        """Test that missing car_id fails."""
        with pytest.raises(ValidationError):
            DealerDetailsRequest(dealer_id="D-001")


class TestScheduleCallRequest:
    """Tests for ScheduleCallRequest DTO."""

    def test_valid_request(self):
        """Test valid schedule call request."""
        req = ScheduleCallRequest(
            dealer_id="D-001",
            car_id="C-001",
            date_raw="tomorrow",
            time_raw="3pm",
            timezone="America/New_York",
        )
        assert req.dealer_id == "D-001"
        assert req.car_id == "C-001"
        assert req.date_raw == "tomorrow"
        assert req.time_raw == "3pm"
        assert req.timezone == "America/New_York"

    def test_default_timezone(self):
        """Test that timezone defaults to UTC."""
        req = ScheduleCallRequest(
            dealer_id="D-001",
            car_id="C-001",
            date_raw="2024-12-25",
            time_raw="15:00",
        )
        assert req.timezone == "UTC"

    def test_date_raw_empty_fails(self):
        """Test that empty date_raw is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ScheduleCallRequest(
                dealer_id="D-001",
                car_id="C-001",
                date_raw="",
                time_raw="3pm",
            )
        assert "String should have at least 1 character" in str(exc_info.value)

    def test_time_raw_empty_fails(self):
        """Test that empty time_raw is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ScheduleCallRequest(
                dealer_id="D-001",
                car_id="C-001",
                date_raw="tomorrow",
                time_raw="",
            )
        assert "String should have at least 1 character" in str(exc_info.value)

    def test_date_raw_max_length(self):
        """Test that date_raw respects max length."""
        req = ScheduleCallRequest(
            dealer_id="D-001",
            car_id="C-001",
            date_raw="x" * 200,
            time_raw="3pm",
        )
        assert req.date_raw == "x" * 200


class TestSessionRequest:
    """Tests for SessionRequest DTO."""

    def test_valid_request(self):
        """Test valid session request."""
        req = SessionRequest(session_id="sess_123", user_id="user_456")
        assert req.session_id == "sess_123"
        assert req.user_id == "user_456"

    def test_missing_session_id_fails(self):
        """Test that missing session_id fails."""
        with pytest.raises(ValidationError):
            SessionRequest(user_id="user_456")

    def test_user_id_optional(self):
        """Test that user_id is optional."""
        req = SessionRequest(session_id="sess_123")
        assert req.session_id == "sess_123"
        assert req.user_id is None


class TestCreateSessionRequest:
    """Tests for CreateSessionRequest DTO."""

    def test_valid_with_user_id(self):
        """Test creating a new session with user_id."""
        req = CreateSessionRequest(user_id="user_123")
        assert req.user_id == "user_123"

    def test_valid_without_user_id(self):
        """Test creating a new session without user_id."""
        req = CreateSessionRequest()
        assert req.user_id is None

    def test_user_id_optional(self):
        """Test that user_id is optional."""
        req = CreateSessionRequest(user_id=None)
        assert req.user_id is None
