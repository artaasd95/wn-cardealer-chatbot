from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from models.inputs.car import CarExtraction, NormalizedCarQuery
from models.inputs.dealer import DealerQuery
from models.inputs.schedule import ScheduleExtraction
from models.inputs.session import SchedulingContext, SessionContext
from models.inputs.task import TaskDecision
from models.outputs.car import CarRecord, CarSearchResult
from models.outputs.dealer import DealerRecord, DealerWithCars
from models.outputs.schedule import ScheduleRecord
from models.outputs.session import MessageRecord, SessionRecord, SessionSnapshotRecord


class TestSchedulingContext:
    """Tests for SchedulingContext model."""

    def test_valid_full_context(self):
        """Test creating a full SchedulingContext."""
        ctx = SchedulingContext(
            date_raw="tomorrow",
            time_raw="3pm",
            timezone="America/New_York",
        )
        assert ctx.date_raw == "tomorrow"
        assert ctx.time_raw == "3pm"
        assert ctx.timezone == "America/New_York"

    def test_default_timezone(self):
        """Test that timezone defaults to UTC."""
        ctx = SchedulingContext()
        assert ctx.timezone == "UTC"

    def test_partial_context(self):
        """Test creating a partial SchedulingContext."""
        ctx = SchedulingContext(date_raw="tomorrow")
        assert ctx.date_raw == "tomorrow"
        assert ctx.time_raw is None
        assert ctx.timezone == "UTC"


class TestSessionContext:
    """Tests for SessionContext model."""

    def test_valid_context(self):
        """Test creating a valid SessionContext."""
        ctx = SessionContext(
            session_id="sess_123",
            workflow_state="CAR_SELECTED",
            selected_car_id="C-001",
            selected_dealer_id="D-001",
        )
        assert ctx.session_id == "sess_123"
        assert ctx.workflow_state == "CAR_SELECTED"
        assert ctx.selected_car_id == "C-001"
        assert ctx.selected_dealer_id == "D-001"

    def test_empty_history_default(self):
        """Test that conversation_history defaults to empty list."""
        ctx = SessionContext(
            session_id="sess_123",
            workflow_state="START",
        )
        assert ctx.conversation_history == []

    def test_scheduling_context_default(self):
        """Test that scheduling_context defaults to SchedulingContext()."""
        ctx = SessionContext(
            session_id="sess_123",
            workflow_state="AWAITING_DATETIME",
        )
        assert isinstance(ctx.scheduling_context, SchedulingContext)
        assert ctx.scheduling_context.timezone == "UTC"


class TestCarExtraction:
    """Tests for CarExtraction model."""

    def test_full_extraction(self):
        """Test full car extraction from LLM."""
        ext = CarExtraction(
            make="BMW",
            model="3-Series",
            variant="xDrive",
            year_from=2020,
            year_to=2024,
        )
        assert ext.make == "BMW"
        assert ext.model == "3-Series"
        assert ext.variant == "xDrive"
        assert ext.year_from == 2020
        assert ext.year_to == 2024

    def test_partial_extraction(self):
        """Test partial extraction (only make)."""
        ext = CarExtraction(make="BMW")
        assert ext.make == "BMW"
        assert ext.model is None
        assert ext.variant is None

    def test_all_optional(self):
        """Test that all fields are optional."""
        ext = CarExtraction()
        assert ext.make is None
        assert ext.model is None


class TestNormalizedCarQuery:
    """Tests for NormalizedCarQuery model."""

    def test_normalized_query(self):
        """Test a normalized query."""
        query = NormalizedCarQuery(
            make="BMW",
            model="3-Series",
            year_from=2020,
        )
        assert query.make == "BMW"
        assert query.model == "3-Series"
        assert query.year_from == 2020


class TestDealerQuery:
    """Tests for DealerQuery model."""

    def test_by_dealer_id(self):
        """Test dealer query by ID."""
        query = DealerQuery(dealer_id="D-001")
        assert query.dealer_id == "D-001"
        assert query.city is None

    def test_by_city(self):
        """Test dealer query by city."""
        query = DealerQuery(city="New York")
        assert query.dealer_id is None
        assert query.city == "New York"

    def test_both_optional(self):
        """Test that both fields are optional."""
        query = DealerQuery()
        assert query.dealer_id is None
        assert query.city is None


class TestScheduleExtraction:
    """Tests for ScheduleExtraction model."""

    def test_full_extraction(self):
        """Test full schedule extraction."""
        ext = ScheduleExtraction(
            date_raw="2024-12-25",
            time_raw="15:00",
            timezone="America/New_York",
            confidence=0.95,
        )
        assert ext.date_raw == "2024-12-25"
        assert ext.time_raw == "15:00"
        assert ext.timezone == "America/New_York"
        assert ext.confidence == 0.95

    def test_default_confidence(self):
        """Test that confidence defaults to 0.0."""
        ext = ScheduleExtraction(date_raw="tomorrow")
        assert ext.confidence == 0.0

    def test_confidence_bounds(self):
        """Test confidence bounds validation."""
        # Valid: 0.0
        ext = ScheduleExtraction(confidence=0.0)
        assert ext.confidence == 0.0

        # Valid: 1.0
        ext = ScheduleExtraction(confidence=1.0)
        assert ext.confidence == 1.0

        # Invalid: > 1.0
        with pytest.raises(ValidationError):
            ScheduleExtraction(confidence=1.1)


class TestTaskDecision:
    """Tests for TaskDecision model."""

    def test_valid_decision(self):
        """Test a valid task decision."""
        decision = TaskDecision(
            task_type="ITEM_LOOKUP",
            confidence=0.95,
            reason="User asked for a car search",
        )
        assert decision.task_type == "ITEM_LOOKUP"
        assert decision.confidence == 0.95
        assert decision.reason == "User asked for a car search"

    def test_default_confidence(self):
        """Test that confidence defaults to 0.5."""
        decision = TaskDecision(task_type="UNKNOWN")
        assert decision.confidence == 0.5

    def test_reason_optional(self):
        """Test that reason is optional."""
        decision = TaskDecision(task_type="DEALER_DETAILS")
        assert decision.reason is None


class TestMessageRecord:
    """Tests for MessageRecord model."""

    def test_valid_message(self):
        """Test a valid message record."""
        now = datetime.now(UTC).replace(tzinfo=None)
        msg = MessageRecord(
            role="user",
            content="I'm looking for a BMW",
            created_at=now,
        )
        assert msg.role == "user"
        assert msg.content == "I'm looking for a BMW"
        assert msg.created_at == now

    def test_default_created_at(self):
        """Test that created_at defaults to current time."""
        msg = MessageRecord(role="assistant", content="Hello")
        assert isinstance(msg.created_at, datetime)

    def test_assistant_role(self):
        """Test assistant role."""
        msg = MessageRecord(role="assistant", content="Found a car")
        assert msg.role == "assistant"


class TestSessionRecord:
    """Tests for SessionRecord model."""

    def test_valid_record(self):
        """Test a valid session record."""
        rec = SessionRecord(
            session_id="sess_123",
            user_id="user_456",
            workflow_state="CAR_SELECTED",
            selected_car_id="C-001",
            selected_dealer_id="D-001",
        )
        assert rec.session_id == "sess_123"
        assert rec.user_id == "user_456"
        assert rec.workflow_state == "CAR_SELECTED"

    def test_default_timestamps(self):
        """Test that timestamps default to current time."""
        rec = SessionRecord(
            session_id="sess_123",
            workflow_state="START",
        )
        assert isinstance(rec.created_at, datetime)
        assert isinstance(rec.updated_at, datetime)

    def test_history_default(self):
        """Test that conversation_history defaults to empty."""
        rec = SessionRecord(
            session_id="sess_123",
            workflow_state="START",
        )
        assert rec.conversation_history == []


class TestSessionSnapshotRecord:
    """Tests for SessionSnapshotRecord model."""

    def test_valid_snapshot(self):
        """Test a valid session snapshot record."""
        snap = SessionSnapshotRecord(
            session_id="sess_123",
            workflow_state="CAR_SELECTED",
            selected_car_id="C-001",
            selected_dealer_id="D-001",
            conversation_history=[],
            scheduling_context={},
            user_id="user_456",
            expires_at=None,
        )
        assert snap.session_id == "sess_123"
        assert snap.workflow_state == "CAR_SELECTED"


class TestCarRecord:
    """Tests for CarRecord model."""

    def test_valid_record(self):
        """Test a valid car record."""
        rec = CarRecord(
            car_id="C-001",
            make="BMW",
            model="3-Series",
            variant="xDrive",
            year=2023,
            fuel_type="Gasoline",
            transmission="Automatic",
            body_type="Sedan",
            price_min=35000.0,
            price_max=45000.0,
            mileage_km=15000,
            features="Sunroof, Navigation",
            dealer_id="D-001",
        )
        assert rec.car_id == "C-001"
        assert rec.make == "BMW"
        assert rec.year == 2023

    def test_minimal_record(self):
        """Test a minimal car record."""
        rec = CarRecord(
            car_id="C-001",
            make="BMW",
            model="3-Series",
            year=2023,
            dealer_id="D-001",
        )
        assert rec.car_id == "C-001"
        assert rec.variant is None
        assert rec.price_min is None


class TestCarSearchResult:
    """Tests for CarSearchResult model."""

    def test_found_status(self):
        """Test search result with found status."""
        result = CarSearchResult(
            status="found",
            cars=[
                CarRecord(
                    car_id="C-001",
                    make="BMW",
                    model="3-Series",
                    year=2023,
                    dealer_id="D-001",
                )
            ],
        )
        assert result.status == "found"
        assert len(result.cars) == 1

    def test_not_found_status(self):
        """Test search result with not_found status."""
        result = CarSearchResult(status="not_found")
        assert result.status == "not_found"
        assert result.cars == []

    def test_multiple_status(self):
        """Test search result with multiple status."""
        cars = [
            CarRecord(
                car_id="C-001",
                make="BMW",
                model="3-Series",
                year=2023,
                dealer_id="D-001",
            ),
            CarRecord(
                car_id="C-002",
                make="BMW",
                model="3-Series",
                year=2024,
                dealer_id="D-001",
            ),
        ]
        result = CarSearchResult(
            status="multiple",
            cars=cars,
            candidates=cars,
        )
        assert result.status == "multiple"
        assert len(result.cars) == 2
        assert len(result.candidates) == 2


class TestDealerRecord:
    """Tests for DealerRecord model."""

    def test_valid_record(self):
        """Test a valid dealer record."""
        rec = DealerRecord(
            dealer_id="D-001",
            dealer_name="Downtown BMW",
            city="New York",
            state="NY",
            address="123 Main St",
            phone="+1-555-0100",
            email="sales@downtownbmw.com",
            rating=4.7,
        )
        assert rec.dealer_id == "D-001"
        assert rec.dealer_name == "Downtown BMW"
        assert rec.rating == 4.7

    def test_minimal_record(self):
        """Test a minimal dealer record."""
        rec = DealerRecord(
            dealer_id="D-001",
            dealer_name="BMW",
            city="New York",
            address="123 Main St",
            phone="+1-555-0100",
            email="sales@bmw.com",
        )
        assert rec.state is None
        assert rec.rating is None


class TestDealerWithCars:
    """Tests for DealerWithCars model."""

    def test_valid_composite(self):
        """Test a valid dealer with cars."""
        dealer = DealerRecord(
            dealer_id="D-001",
            dealer_name="Downtown BMW",
            city="New York",
            address="123 Main St",
            phone="+1-555-0100",
            email="sales@downtownbmw.com",
        )
        cars = [
            CarRecord(
                car_id="C-001",
                make="BMW",
                model="3-Series",
                year=2023,
                dealer_id="D-001",
            )
        ]
        composite = DealerWithCars(dealer=dealer, cars=cars)
        assert composite.dealer.dealer_id == "D-001"
        assert len(composite.cars) == 1

    def test_dealer_with_no_cars(self):
        """Test dealer with empty cars list."""
        dealer = DealerRecord(
            dealer_id="D-001",
            dealer_name="Downtown BMW",
            city="New York",
            address="123 Main St",
            phone="+1-555-0100",
            email="sales@downtownbmw.com",
        )
        composite = DealerWithCars(dealer=dealer)
        assert len(composite.cars) == 0


class TestScheduleRecord:
    """Tests for ScheduleRecord model."""

    def test_valid_record(self):
        """Test a valid schedule record."""
        scheduled_time = datetime(2024, 12, 26, 15, 0, 0)
        rec = ScheduleRecord(
            schedule_id="sched_123",
            session_id="sess_123",
            dealer_id="D-001",
            car_id="C-001",
            scheduled_for=scheduled_time,
            timezone="America/New_York",
            status="confirmed",
            user_id="user_456",
        )
        assert rec.schedule_id == "sched_123"
        assert rec.dealer_id == "D-001"
        assert rec.status == "confirmed"

    def test_default_status(self):
        """Test that status defaults to confirmed."""
        scheduled_time = datetime(2024, 12, 26, 15, 0, 0)
        rec = ScheduleRecord(
            schedule_id="sched_123",
            session_id="sess_123",
            dealer_id="D-001",
            car_id="C-001",
            scheduled_for=scheduled_time,
        )
        assert rec.status == "confirmed"

    def test_default_created_at(self):
        """Test that created_at defaults to current time."""
        scheduled_time = datetime(2024, 12, 26, 15, 0, 0)
        rec = ScheduleRecord(
            schedule_id="sched_123",
            session_id="sess_123",
            dealer_id="D-001",
            car_id="C-001",
            scheduled_for=scheduled_time,
        )
        assert isinstance(rec.created_at, datetime)
