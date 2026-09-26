"""Schedule call use case.

Orchestrates the scheduling workflow, plan steps 1-9:

1. extract date/time/timezone via LLMPort (raw text kept for ambiguity checks)
2. merge with anything collected on an earlier turn (scheduling context)
3. resolve the timezone, or ask which one was meant
4. parse; missing fields ask only for what is missing, ambiguity asks a
   clarification question, unreadable text asks again
5. validate through the domain entity (past times are rejected before any
   persistence)
6. build the ScheduleRecord, persist it through the ScheduleRepository port
7. word the confirmation through LLMPort (deterministic fallback on failure)

No real external booking is made: the record is stored locally only.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from application.tasks.schedule_call.workflow import ScheduleCallWorkflow
from domain.entities.schedule import (
    Schedule,
    parse_schedule_when,
    resolve_timezone,
    to_utc_naive,
)
from domain.enums.workflow_state import WorkflowState
from domain.exceptions import DomainError, InvalidScheduleError
from DTO.outputs.schedule import ScheduleConfirmation
from infrastructure.llm.prompts.response import build_response_prompt
from infrastructure.llm.prompts.schedule_extraction import build_schedule_extraction_prompt
from models.inputs.response import ResponseWording
from models.inputs.schedule import ScheduleExtraction, SchedulingContext
from models.outputs.schedule import ScheduleOutcome, ScheduleRecord
from ports.llm import LLMPort
from ports.repositories.schedule_repository import ScheduleRepository

logger = logging.getLogger(__name__)


class ScheduleCallUseCase:
    """Execute call scheduling workflow."""

    def __init__(
        self,
        llm: LLMPort,
        schedule_repo: ScheduleRepository | None = None,
    ) -> None:
        """Initialize with dependencies.

        Args:
            llm: LLMPort for extraction and confirmation wording.
            schedule_repo: Repository used to persist the created schedule.
                When None the schedule is built but not stored (the plan's
                "no real booking" path used by isolated tests).
        """
        self.llm = llm
        self.schedule_repo = schedule_repo

    def execute(
        self,
        user_message: str,
        dealer_id: str,
        car_id: str,
        session_id: str,
        scheduling_context: dict[str, str | None] | None = None,
    ) -> tuple[ScheduleOutcome, WorkflowState]:
        """Execute the schedule call workflow.

        Args:
            user_message: The user's raw input about scheduling.
            dealer_id: The selected dealer ID (already guarded by the caller).
            car_id: The selected car ID (already guarded by the caller).
            session_id: The session the schedule belongs to.
            scheduling_context: Partial date/time collected on earlier turns.

        Returns:
            Tuple of (outcome for this turn, next workflow state).
        """
        # Step 1: extract raw date/time/timezone via LLMPort
        extraction = self.llm.structured_completion(
            build_schedule_extraction_prompt(user_message), ScheduleExtraction
        )

        # Step 2: merge with what earlier turns already collected — a new
        # utterance overrides a field it actually mentions, everything else
        # carries over, so "tomorrow" then "3pm" completes one request.
        prior = SchedulingContext.model_validate(dict(scheduling_context or {}))
        date_raw = (extraction.date_raw or "").strip() or (prior.date_raw or "").strip()
        time_raw = (extraction.time_raw or "").strip() or (prior.time_raw or "").strip()
        timezone_text = (extraction.timezone or "").strip() or (prior.timezone or "").strip()

        context = {
            "date_raw": date_raw or None,
            "time_raw": time_raw or None,
            "timezone": timezone_text or None,
        }

        # Step 3: timezone — unknown text is clarified, never guessed
        timezone_name = resolve_timezone(timezone_text)
        if timezone_name is None:
            logger.warning("unrecognized timezone %r", timezone_text)
            return (
                ScheduleOutcome(
                    status="ambiguous",
                    question=(
                        f'I did not recognize the time zone "{timezone_text}". '
                        "Which one should I use (for example UTC, Europe/Berlin, "
                        "America/New_York)?"
                    ),
                    missing_fields=["timezone"],
                    context=context,
                ),
                WorkflowState.AWAITING_DATETIME,
            )

        # Step 4: parse — ask only for what is missing, clarify ambiguity
        parsed = parse_schedule_when(date_raw, time_raw)
        if parsed.missing:
            logger.info("incomplete scheduling input (missing %s)", parsed.missing)
            return (
                ScheduleOutcome(
                    status=f"needs_{parsed.missing}",
                    question=parsed.clarification or "Could you add a date and time?",
                    missing_fields=(
                        ["date", "time"] if parsed.missing == "datetime" else [parsed.missing]
                    ),
                    context=context,
                ),
                WorkflowState.AWAITING_DATETIME,
            )
        if parsed.clarification or parsed.value is None:
            return (
                ScheduleOutcome(
                    status=parsed.kind or "ambiguous",
                    question=parsed.clarification or "Could you repeat the date and time?",
                    context=context,
                ),
                WorkflowState.AWAITING_DATETIME,
            )

        # Step 5: domain validation — past times are rejected here, before
        # anything is built or persisted.
        schedule_id = str(uuid4())
        scheduled_for = to_utc_naive(parsed.value, timezone_name)
        entity = Schedule(
            schedule_id=schedule_id,
            dealer_id=dealer_id,
            car_id=car_id,
            scheduled_for=scheduled_for,
            timezone=timezone_name,
            status="pending",
        )
        if not entity.is_future():
            logger.info("rejected past scheduling request: %s", scheduled_for)
            return (
                ScheduleOutcome(
                    status="past",
                    question=(
                        "That time has already passed. What date and time would you like instead?"
                    ),
                    missing_fields=["date", "time"],
                    context=context,
                ),
                WorkflowState.AWAITING_DATETIME,
            )
        try:
            entity.validate()
        except InvalidScheduleError as exc:
            logger.warning("schedule rejected by domain rules: %s", exc)
            return (
                ScheduleOutcome(
                    status="invalid",
                    question=(
                        "I could not accept that appointment "
                        f"({exc}). Could you give me another date and time?"
                    ),
                    missing_fields=["date", "time"],
                    context=context,
                ),
                WorkflowState.AWAITING_DATETIME,
            )

        # Step 6: build the record and persist it through the port
        record = ScheduleRecord(
            schedule_id=schedule_id,
            session_id=session_id,
            dealer_id=dealer_id,
            car_id=car_id,
            scheduled_for=scheduled_for,
            timezone=timezone_name,
            status="pending",
        )
        if self.schedule_repo is not None:
            try:
                record = self.schedule_repo.save(record)
            except DomainError as exc:
                logger.error("could not persist schedule: %s", exc)
                return (
                    ScheduleOutcome(
                        status="failed",
                        question=(
                            "I built the appointment but could not save it. "
                            "Please try again in a moment."
                        ),
                        context=context,
                    ),
                    WorkflowState.AWAITING_DATETIME,
                )
        else:
            logger.warning("no schedule repository wired; schedule not persisted")

        # Step 7: confirmation wording via LLMPort (DTO → prompt → text)
        confirmation = ScheduleConfirmation(
            dealer_id=record.dealer_id,
            car_id=record.car_id,
            scheduled_for=record.scheduled_for,
            timezone=record.timezone,
            status=record.status,
        )
        return (
            ScheduleOutcome(
                status="created",
                record=record,
                reply=self._word_confirmation(confirmation),
                context={},
            ),
            ScheduleCallWorkflow.advance(schedule_created=True),
        )

    def _word_confirmation(self, confirmation: ScheduleConfirmation) -> str:
        """Word a scheduling confirmation through the LLM.

        Args:
            confirmation: The DTO built from the persisted record.

        Returns:
            LLM wording, or a deterministic fallback built from the same DTO
            when the provider fails or returns nothing.
        """
        data_summary = (
            f"dealer id: {confirmation.dealer_id}; car id: {confirmation.car_id}; "
            f"date and time: {confirmation.scheduled_for.isoformat()} UTC; "
            f"local time zone: {confirmation.timezone}; status: {confirmation.status}"
        )
        prompt = build_response_prompt(
            task_summary=(
                "The user's call has been scheduled. Confirm it and say exactly when it happens."
            ),
            data_summary=data_summary,
        )
        worded = self.llm.structured_completion(prompt, ResponseWording).reply.strip()
        if worded:
            return worded

        when = confirmation.scheduled_for.strftime("%A, %B %d, %Y at %H:%M UTC")
        return (
            f"Your call is booked for {when} "
            f"({confirmation.timezone} local time). Anything else I can help with?"
        )
