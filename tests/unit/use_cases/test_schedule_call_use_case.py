"""Tests for application/use_cases/schedule_call.py.

Every branch of the schedule flow from plan.md: missing fields, ambiguity,
unreadable input, past times, persistence failure, context carry-over and the
two plan-labelled utterances ("tomorrow afternoon", "Friday at 3").
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from application.use_cases.schedule_call import ScheduleCallUseCase
from domain.enums.workflow_state import WorkflowState
from domain.exceptions import DomainError
from tests.fakes import (
    FakeLLM,
    StubScheduleRepository,
    now_utc,
    schedule_extraction,
    wording_reply,
)

pytestmark = pytest.mark.unit

FUTURE_DATE = "2030-05-15"


class TestScheduleCallUseCaseCreated:
    """The created branch: build, validate, persist, word."""

    def test_creates_and_persists_schedule(self, fake_llm: FakeLLM) -> None:
        """Happy path: a complete request becomes a persisted record."""
        repo = StubScheduleRepository()
        fake_llm.enqueue(schedule_extraction(FUTURE_DATE, "15:00", "UTC"))
        fake_llm.enqueue(wording_reply("Your call is booked for May 15, 2030."))

        outcome, next_state = ScheduleCallUseCase(fake_llm, repo).execute(
            "book a call on 2030-05-15 at 3pm UTC",
            "D-003",
            "C-0003",
            "sess-1",
        )

        assert outcome.status == "created"
        assert outcome.reply == "Your call is booked for May 15, 2030."
        assert outcome.record is not None
        assert next_state is WorkflowState.SCHEDULE_CONFIRMED
        assert len(repo.saved) == 1
        assert repo.saved[0].dealer_id == "D-003"
        assert repo.saved[0].car_id == "C-0003"
        assert repo.saved[0].session_id == "sess-1"
        assert repo.saved[0].scheduled_for.hour == 15

    def test_empty_llm_wording_falls_back_to_deterministic_confirmation(
        self, fake_llm: FakeLLM
    ) -> None:
        """Failure branch: a dead provider still produces a usable confirmation."""
        fake_llm.enqueue(schedule_extraction(FUTURE_DATE, "15:00", "UTC"))
        fake_llm.enqueue(wording_reply(""))

        outcome, _ = ScheduleCallUseCase(fake_llm, StubScheduleRepository()).execute(
            "2030-05-15 at 3pm", "D-003", "C-0003", "sess-1"
        )

        assert outcome.status == "created"
        assert outcome.reply.startswith("Your call is booked for")

    def test_no_repository_still_builds_schedule(self, fake_llm: FakeLLM) -> None:
        """Plan path: with no repository wired the call is built, not stored."""
        fake_llm.enqueue(schedule_extraction(FUTURE_DATE, "15:00", "UTC"))
        fake_llm.enqueue(wording_reply(""))

        outcome, next_state = ScheduleCallUseCase(fake_llm, None).execute(
            "2030-05-15 at 3pm", "D-003", "C-0003", "sess-1"
        )

        assert outcome.status == "created"
        assert outcome.record is not None
        assert next_state is WorkflowState.SCHEDULE_CONFIRMED


class TestScheduleCallUseCaseMissingFields:
    """Missing date / missing time / both: ask only for what is missing."""

    def test_missing_date_asks_only_for_the_date(self, fake_llm: FakeLLM) -> None:
        """Edge: a time without a date asks for the date and keeps the time."""
        fake_llm.enqueue(schedule_extraction(None, "15:00"))

        outcome, next_state = ScheduleCallUseCase(fake_llm, StubScheduleRepository()).execute(
            "at 3pm", "D-003", "C-0003", "sess-1"
        )

        assert outcome.status == "needs_date"
        assert outcome.missing_fields == ["date"]
        assert "What date" in outcome.question
        assert "15:00" in outcome.question
        assert next_state is WorkflowState.AWAITING_DATETIME

    def test_missing_time_asks_only_for_the_time(self, fake_llm: FakeLLM) -> None:
        """Edge: a date without a time asks for the time and keeps the date."""
        fake_llm.enqueue(schedule_extraction("tomorrow", None))

        outcome, _ = ScheduleCallUseCase(fake_llm, StubScheduleRepository()).execute(
            "tomorrow", "D-003", "C-0003", "sess-1"
        )

        assert outcome.status == "needs_time"
        assert outcome.missing_fields == ["time"]
        assert "What time on tomorrow" in outcome.question

    def test_missing_both_asks_for_date_and_time(self, fake_llm: FakeLLM) -> None:
        """Edge: nothing extracted asks for the whole date-time."""
        fake_llm.enqueue(schedule_extraction(None, None))

        outcome, _ = ScheduleCallUseCase(fake_llm, StubScheduleRepository()).execute(
            "schedule a call", "D-003", "C-0003", "sess-1"
        )

        assert outcome.status == "needs_datetime"
        assert outcome.missing_fields == ["date", "time"]
        assert "What date and time" in outcome.question


class TestScheduleCallUseCaseAmbiguity:
    """Ambiguous date / time / timezone: clarify, never guess."""

    def test_ambiguous_date_clarifies(self, fake_llm: FakeLLM) -> None:
        """Edge: 10/01 could be day-first or month-first."""
        fake_llm.enqueue(schedule_extraction("10/01/2027", "15:00"))

        outcome, _ = ScheduleCallUseCase(fake_llm, StubScheduleRepository()).execute(
            "10/01/2027 at 3pm", "D-003", "C-0003", "sess-1"
        )

        assert outcome.status == "ambiguous"
        assert "day-first or month-first" in outcome.question

    def test_ambiguous_hour_clarifies(self, fake_llm: FakeLLM) -> None:
        """Edge: '3' without am/pm is not silently guessed."""
        fake_llm.enqueue(schedule_extraction("tomorrow", "3"))

        outcome, _ = ScheduleCallUseCase(fake_llm, StubScheduleRepository()).execute(
            "tomorrow at 3", "D-003", "C-0003", "sess-1"
        )

        assert outcome.status == "ambiguous"
        assert "morning or in the afternoon" in outcome.question

    def test_tomorrow_afternoon_asks_for_the_hour(self, fake_llm: FakeLLM) -> None:
        """Plan-labelled case: 'tomorrow afternoon' needs a concrete hour."""
        fake_llm.enqueue(schedule_extraction("tomorrow", "afternoon"))

        outcome, _ = ScheduleCallUseCase(fake_llm, StubScheduleRepository()).execute(
            "tomorrow afternoon", "D-003", "C-0003", "sess-1"
        )

        assert outcome.status == "ambiguous"
        assert "What time in the afternoon" in outcome.question

    def test_friday_at_three_asks_morning_or_afternoon(self, fake_llm: FakeLLM) -> None:
        """Plan-labelled case: 'Friday at 3' needs morning/afternoon."""
        fake_llm.enqueue(schedule_extraction("Friday", "3"))

        outcome, _ = ScheduleCallUseCase(fake_llm, StubScheduleRepository()).execute(
            "Friday at 3", "D-003", "C-0003", "sess-1"
        )

        assert outcome.status == "ambiguous"
        assert "morning or in the afternoon" in outcome.question

    def test_unrecognized_timezone_is_clarified(self, fake_llm: FakeLLM) -> None:
        """Edge: an unknown timezone text is never silently defaulted."""
        fake_llm.enqueue(schedule_extraction(FUTURE_DATE, "15:00", "Middle Earth"))

        outcome, _ = ScheduleCallUseCase(fake_llm, StubScheduleRepository()).execute(
            "2030-05-15 at 3pm Middle Earth time", "D-003", "C-0003", "sess-1"
        )

        assert outcome.status == "ambiguous"
        assert outcome.missing_fields == ["timezone"]
        assert "time zone" in outcome.question


class TestScheduleCallUseCaseRejected:
    """Past, unreadable and unpersistable requests."""

    def test_past_date_is_rejected_before_persistence(self, fake_llm: FakeLLM) -> None:
        """Edge: a past time is refused by the domain before any write."""
        repo = StubScheduleRepository()
        fake_llm.enqueue(schedule_extraction("2020-01-01", "10am"))

        outcome, next_state = ScheduleCallUseCase(fake_llm, repo).execute(
            "2020-01-01 at 10am", "D-003", "C-0003", "sess-1"
        )

        assert outcome.status == "past"
        assert "already passed" in outcome.question
        assert repo.saved == []
        assert next_state is WorkflowState.AWAITING_DATETIME

    def test_unreadable_date_is_rejected(self, fake_llm: FakeLLM) -> None:
        """Edge: an invalid date asks again instead of guessing."""
        fake_llm.enqueue(schedule_extraction("32 Octember", "10am"))

        outcome, _ = ScheduleCallUseCase(fake_llm, StubScheduleRepository()).execute(
            "the 32nd of Octember at 10am", "D-003", "C-0003", "sess-1"
        )

        assert outcome.status == "invalid"
        assert "could not read the date" in outcome.question

    def test_unreadable_time_is_rejected(self, fake_llm: FakeLLM) -> None:
        """Edge: an invalid time asks again instead of guessing."""
        fake_llm.enqueue(schedule_extraction(FUTURE_DATE, "25:99"))

        outcome, _ = ScheduleCallUseCase(fake_llm, StubScheduleRepository()).execute(
            "2030-05-15 at 25:99", "D-003", "C-0003", "sess-1"
        )

        assert outcome.status == "invalid"
        assert "could not read the time" in outcome.question

    def test_persistence_failure_degrades_to_a_question(self, fake_llm: FakeLLM) -> None:
        """Failure branch: a repository error becomes a polite retry question."""
        repo = StubScheduleRepository(error=DomainError("Could not store the schedule"))
        fake_llm.enqueue(schedule_extraction(FUTURE_DATE, "15:00"))
        fake_llm.enqueue(wording_reply(""))

        outcome, next_state = ScheduleCallUseCase(fake_llm, repo).execute(
            "2030-05-15 at 3pm", "D-003", "C-0003", "sess-1"
        )

        assert outcome.status == "failed"
        assert "could not save it" in outcome.question
        assert next_state is WorkflowState.AWAITING_DATETIME


class TestScheduleCallUseCaseContext:
    """Partial collection across turns and user changes."""

    def test_date_collected_earlier_completes_with_time(self, fake_llm: FakeLLM) -> None:
        """Context carry-over: 'tomorrow' then '3pm' completes one request."""
        fake_llm.enqueue(schedule_extraction(None, "15:00"))
        fake_llm.enqueue(wording_reply(""))

        outcome, next_state = ScheduleCallUseCase(fake_llm, StubScheduleRepository()).execute(
            "at 3pm",
            "D-003",
            "C-0003",
            "sess-1",
            scheduling_context={"date_raw": "tomorrow", "time_raw": None, "timezone": "UTC"},
        )

        assert outcome.status == "created"
        assert next_state is WorkflowState.SCHEDULE_CONFIRMED
        assert outcome.record is not None
        expected = (now_utc() + timedelta(days=1)).date()
        assert outcome.record.scheduled_for.date() == expected

    def test_user_changes_requested_time(self, fake_llm: FakeLLM) -> None:
        """Edge: a newly mentioned time overrides the collected one."""
        fake_llm.enqueue(schedule_extraction(None, "17:00"))
        fake_llm.enqueue(wording_reply(""))

        outcome, _ = ScheduleCallUseCase(fake_llm, StubScheduleRepository()).execute(
            "actually make it 5pm",
            "D-003",
            "C-0003",
            "sess-1",
            scheduling_context={"date_raw": FUTURE_DATE, "time_raw": "15:00", "timezone": "UTC"},
        )

        assert outcome.status == "created"
        assert outcome.record is not None
        assert outcome.record.scheduled_for.hour == 17

    def test_context_is_cleared_after_creation(self, fake_llm: FakeLLM) -> None:
        """A created schedule leaves no stale date/time behind."""
        fake_llm.enqueue(schedule_extraction(FUTURE_DATE, "15:00"))
        fake_llm.enqueue(wording_reply(""))

        outcome, _ = ScheduleCallUseCase(fake_llm, StubScheduleRepository()).execute(
            "2030-05-15 at 3pm",
            "D-003",
            "C-0003",
            "sess-1",
            scheduling_context={"date_raw": "yesterday", "time_raw": "9am", "timezone": "UTC"},
        )

        assert outcome.status == "created"
        assert outcome.context == {}
