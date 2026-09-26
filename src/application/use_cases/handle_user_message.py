"""Handle user message use case.

Orchestrates a full chat turn: load session, select task, dispatch, save session.

Each task handler returns the reply text, the next workflow state and — when
the default "next tasks" suggestion does not fit — an explicit list of
suggested actions (disambiguation candidates, for example). Models are mapped
to DTOs here, at the application edge, before anything reaches the API.
"""

from __future__ import annotations

import logging

from application.session.service import SessionService
from application.use_cases.get_dealer_details import GetDealerDetailsUseCase
from application.use_cases.load_session import LoadSessionUseCase
from application.use_cases.lookup_car import LookupCarUseCase
from application.use_cases.save_session import SaveSessionUseCase
from application.use_cases.schedule_call import ScheduleCallUseCase
from application.use_cases.select_task import SelectTaskUseCase
from domain.enums.task_type import TaskType
from domain.enums.workflow_state import WorkflowState
from domain.exceptions import DomainError
from DTO.inputs.chat import ChatRequest
from DTO.outputs.car import CarCandidateList, CarSummary
from DTO.outputs.chat import ChatResponse, ClarificationMessage
from DTO.outputs.dealer import DealerDetails
from infrastructure.llm.prompts.conversation import build_conversation_prompt
from infrastructure.llm.prompts.response import build_response_prompt
from models.inputs.response import ResponseWording
from models.outputs.car import CarRecord
from models.outputs.dealer import DealerRecord
from models.outputs.session import SessionRecord
from ports.llm import LLMPort
from ports.repositories.car_repository import CarRepository
from ports.repositories.dealer_repository import DealerRepository
from ports.repositories.schedule_repository import ScheduleRepository
from ports.session_store import SessionStore

logger = logging.getLogger(__name__)

_FIND_A_CAR = "Find a car"
_FIND_ANOTHER_CAR = "Find another car"
_GET_DETAILS = "Get dealer details"
_SCHEDULE_CALL = "Schedule a call"


def suggest_next_tasks(state: WorkflowState) -> list[str]:
    """Map the current workflow state to the actions the user can take next.

    Args:
        state: The workflow state the session is in after the turn.

    Returns:
        Human-readable next actions (empty when the bot just asked a question
        the user should answer directly).
    """
    if state in {WorkflowState.START, WorkflowState.AWAITING_CAR, WorkflowState.CAR_NOT_FOUND}:
        return [_FIND_A_CAR]
    if state in {WorkflowState.AWAITING_ACTION, WorkflowState.CAR_SELECTED}:
        return [_GET_DETAILS, _SCHEDULE_CALL, _FIND_ANOTHER_CAR]
    if state is WorkflowState.DEALER_DETAILS_SHOWN:
        return [_SCHEDULE_CALL, _FIND_ANOTHER_CAR]
    if state in {WorkflowState.SCHEDULE_CONFIRMED, WorkflowState.COMPLETE}:
        return [_FIND_ANOTHER_CAR, _GET_DETAILS]
    return []


def _price_range(car: CarRecord) -> str:
    """Format a car's price band for the CarSummary DTO.

    Args:
        car: The car record returned by the repository.

    Returns:
        A printable price range, or a neutral placeholder when unpersisted.
    """
    low, high = car.price_min, car.price_max
    if low is not None and high is not None:
        return f"${low:,.0f} - ${high:,.0f}"
    if low is not None:
        return f"From ${low:,.0f}"
    if high is not None:
        return f"Up to ${high:,.0f}"
    return "Ask the dealer"


def _car_summary(car: CarRecord) -> CarSummary:
    """Map a car record to the CarSummary DTO.

    Args:
        car: The car record returned by the repository.

    Returns:
        The CarSummary DTO.
    """
    return CarSummary(
        car_id=car.car_id,
        make=car.make,
        model=car.model,
        variant=car.variant,
        year=car.year,
        price_range=_price_range(car),
    )


def _candidate_label(car: CarSummary) -> str:
    """Build the clickable label for a disambiguation candidate.

    Args:
        car: The candidate summary.

    Returns:
        A label the user can click to pick that car.
    """
    variant = f" {car.variant}" if car.variant else ""
    return f"{car.make} {car.model}{variant} ({car.year})"


def _dealer_details_dto(dealer: DealerRecord) -> DealerDetails:
    """Map a dealer record to the DealerDetails DTO.

    Args:
        dealer: The dealer record returned by the repository.

    Returns:
        The DealerDetails DTO.
    """
    return DealerDetails(
        dealer_id=dealer.dealer_id,
        name=dealer.dealer_name,
        city=dealer.city,
        address=dealer.address,
        phone=dealer.phone,
        email=dealer.email,
        rating=dealer.rating,
        cars=[],
    )


def _dealer_details_text(details: DealerDetails) -> str:
    """Deterministic dealer-details wording, used when the LLM is unavailable.

    Args:
        details: The dealer details DTO.

    Returns:
        A readable, line-broken summary of the dealer.
    """
    lines = [
        f"{details.name} ({details.city})",
        details.address,
        f"Phone: {details.phone}",
        f"Email: {details.email}",
    ]
    if details.rating is not None:
        lines.append(f"Rating: {details.rating}/5")
    return "\n".join(lines)


class HandleUserMessageUseCase:
    """Orchestrate a full chat turn."""

    def __init__(
        self,
        session_store: SessionStore,
        llm: LLMPort,
        car_repo: CarRepository,
        dealer_repo: DealerRepository,
        schedule_repo: ScheduleRepository | None = None,
    ) -> None:
        """Initialize with all dependencies.

        Args:
            session_store: SessionStore for session persistence.
            llm: LLMPort for LLM calls.
            car_repo: CarRepository for car search.
            dealer_repo: DealerRepository for dealer lookup.
            schedule_repo: ScheduleRepository for persisting created schedules.
        """
        self.llm = llm
        self.session_service = SessionService(session_store)
        self.load_session = LoadSessionUseCase(session_store)
        self.save_session = SaveSessionUseCase(session_store)
        self.select_task = SelectTaskUseCase(llm)
        self.lookup_car = LookupCarUseCase(llm, car_repo, dealer_repo)
        self.get_dealer_details = GetDealerDetailsUseCase(dealer_repo)
        self.schedule_call = ScheduleCallUseCase(llm, schedule_repo, dealer_repo)

    def execute(self, request: ChatRequest) -> ChatResponse:
        """Handle a user message and return a response.

        Args:
            request: The incoming chat request.

        Returns:
            A ChatResponse with the system's reply and updated state.
        """
        try:
            # Step 1: Load or create session
            session = self.session_service.get_or_create(request.session_id, request.user_id)

            # Step 2: Append user message to history
            session = self.session_service.append_message(session, "user", request.message)

            # Step 3: Select task
            current_state = WorkflowState(session.workflow_state)
            task_type = self.select_task.execute(request.message, current_state)

            # Step 4: Dispatch to task
            reply = "I'm not sure how to help with that."
            next_state = current_state
            suggestions: list[str] | None = None

            if task_type == TaskType.GREETING:
                reply, next_state = self._handle_greeting(session)

            elif task_type == TaskType.CONVERSATION:
                reply, next_state = self._handle_conversation(request.message, session)

            elif task_type == TaskType.ITEM_LOOKUP:
                reply, next_state, session, suggestions = self._handle_item_lookup(
                    request.message, session
                )

            elif task_type == TaskType.DEALER_DETAILS:
                reply, next_state = self._handle_dealer_details(session)

            elif task_type == TaskType.SCHEDULE_CALL:
                reply, next_state, session = self._handle_schedule_call(request.message, session)

            else:
                reply = (
                    "I didn't understand that. I can help you find a car, "
                    "show dealer details, or schedule a call — just let me know!"
                )

            # Step 5: Update session — walk the legal path to the target state
            session = self.session_service.advance_through(session, next_state)
            session = self.session_service.append_message(session, "assistant", reply)

            # Step 6: Persist
            self.session_service.persist(session)

            # Step 7: Build response (models/DTO already mapped by the handlers)
            state = WorkflowState(session.workflow_state)
            return ChatResponse(
                session_id=session.session_id,
                reply=reply,
                workflow_state=session.workflow_state,
                suggested_actions=(
                    suggestions if suggestions is not None else suggest_next_tasks(state)
                ),
                requires_input=True,
            )

        except DomainError as e:
            logger.warning(f"Domain error: {str(e)}")
            return ChatResponse(
                session_id=request.session_id or "unknown",
                reply=f"I encountered an issue: {str(e)}",
                workflow_state="ERROR",
                suggested_actions=[],
                requires_input=True,
            )

        except Exception as e:
            logger.error(f"Unexpected error in handle_user_message: {str(e)}")
            return ChatResponse(
                session_id=request.session_id or "unknown",
                reply="An unexpected error occurred. Please try again.",
                workflow_state="ERROR",
                suggested_actions=[],
                requires_input=True,
            )

    def _handle_item_lookup(
        self, user_message: str, session: SessionRecord
    ) -> tuple[str, WorkflowState, SessionRecord, list[str] | None]:
        """Handle car lookup task.

        Args:
            user_message: The user's input.
            session: Current session record.

        Returns:
            Tuple of (reply, next state, updated session, explicit suggestions
            or None to use the state default).
        """
        try:
            conversation_context: str | None = None
            if WorkflowState(session.workflow_state) is WorkflowState.AWAITING_CAR:
                recent_messages = session.conversation_history[-4:]
                if recent_messages:
                    conversation_context = "\n".join(
                        f"{message.role}: {message.content}" for message in recent_messages
                    )

            result, dealer, next_state = self.lookup_car.execute(
                user_message,
                conversation_context,
            )

            if result.status == "found":
                car = result.cars[0]
                session = self.session_service.set_selected_car(session, car.car_id)
                session = self.session_service.add_seen_car(
                    session, car.car_id, car.make, car.model, car.variant, car.year
                )
                if dealer:
                    session = self.session_service.set_selected_dealer(session, dealer.dealer_id)

                summary = _car_summary(car)
                variant = f" {summary.variant}" if summary.variant else ""
                reply = (
                    f"Found {summary.make} {summary.model}{variant} ({summary.year}) — "
                    f"{summary.price_range}."
                )
                if dealer:
                    reply += f" {dealer.dealer_name} in {dealer.city} can help you with it."
                reply += " Would you like dealer details or to schedule a call?"
                return reply, next_state, session, None

            if result.status == "multiple":
                # Disambiguation branch: DTO candidates become clickable options.
                candidates = [_car_summary(c) for c in (result.candidates or result.cars)]
                for raw_car in result.candidates or result.cars:
                    session = self.session_service.add_seen_car(
                        session,
                        raw_car.car_id,
                        raw_car.make,
                        raw_car.model,
                        raw_car.variant,
                        raw_car.year,
                    )
                options = CarCandidateList(
                    candidates=candidates,
                    message="Which of these did you mean?",
                )
                labels = [_candidate_label(c) for c in options.candidates]
                reply = (
                    "I found several matches. "
                    + options.message
                    + " Pick one: "
                    + "; ".join(labels)
                )
                return reply, next_state, session, labels

            # not_found branch: fallback message, not an exception
            clarification = ClarificationMessage(
                reply=(
                    "I couldn't find a car matching that description. "
                    "Could you try a different make, model or year?"
                ),
                missing_fields=["make", "model"],
            )
            return clarification.reply, next_state, session, None

        except Exception as e:
            logger.error(f"Item lookup failed: {str(e)}")
            return f"Car search failed: {str(e)}", WorkflowState.AWAITING_CAR, session, None

    def _handle_greeting(self, session: SessionRecord) -> tuple[str, WorkflowState]:
        """Return a friendly welcome; stay at the current workflow state."""
        state = WorkflowState(session.workflow_state)
        prompt = build_response_prompt(
            task_summary="The user sent a greeting.",
            data_summary=(
                "Reply with a warm, brief welcome. "
                "Mention you can help find cars, get dealer details, or schedule a call."
            ),
        )
        worded = self.llm.structured_completion(prompt, ResponseWording).reply.strip()
        reply = worded or (
            "Hello! I'm your Car Dealer Assistant. "
            "I can help you find a car, get dealer details, or schedule a call. How can I help?"
        )
        return reply, state

    def _handle_conversation(
        self, user_message: str, session: SessionRecord
    ) -> tuple[str, WorkflowState]:
        """Answer a contextual question using session history and seen cars."""
        state = WorkflowState(session.workflow_state)

        if session.seen_cars:
            lines = []
            for c in session.seen_cars:
                variant = f" {c['variant']}" if c.get("variant") else ""
                lines.append(f"- {c['make']} {c['model']}{variant} ({c.get('year', '?')})")
            seen_summary = "\n".join(lines)
        else:
            seen_summary = ""

        recent = session.conversation_history[-6:]
        history_text = "\n".join(f"{m.role}: {m.content}" for m in recent)

        prompt = build_conversation_prompt(
            user_message=user_message,
            conversation_history=history_text,
            seen_cars_summary=seen_summary,
            current_state=state.value,
        )
        worded = self.llm.structured_completion(prompt, ResponseWording).reply.strip()
        reply = worded or (
            "I don't have enough context to answer that. "
            "Would you like to search for a car?"
        )
        return reply, state

    def _handle_dealer_details(self, session: SessionRecord) -> tuple[str, WorkflowState]:
        """Handle dealer details task.

        Args:
            session: Current session record.

        Returns:
            Tuple of (reply, next state).
        """
        try:
            dealer_id = self.session_service.require_selected_dealer(session)
            dealer, next_state = self.get_dealer_details.execute(dealer_id)

            if not dealer:
                return "Could not retrieve dealer details.", next_state

            details = _dealer_details_dto(dealer)
            return self._word_dealer_details(details), next_state

        except DomainError as e:
            # No dealer selected (or details unavailable): stay put and ask the
            # user to pick a car first.
            return str(e), WorkflowState(session.workflow_state)

        except Exception as e:
            logger.error(f"Dealer details failed: {str(e)}")
            return f"Failed to get dealer details: {str(e)}", WorkflowState.AWAITING_ACTION

    def _word_dealer_details(self, details: DealerDetails) -> str:
        """Word a dealer-details reply through the LLM.

        Args:
            details: The DealerDetails DTO built from the record.

        Returns:
            LLM wording, or deterministic text built from the same DTO when the
            provider fails or returns nothing.
        """
        data_summary = (
            f"name: {details.name}; city: {details.city}; address: {details.address}; "
            f"phone: {details.phone}; email: {details.email}; "
            f"rating: {details.rating if details.rating is not None else 'not rated'}"
        )
        prompt = build_response_prompt(
            task_summary="The user asked for the dealer's contact details.",
            data_summary=data_summary,
        )
        worded = self.llm.structured_completion(prompt, ResponseWording).reply.strip()
        return worded or _dealer_details_text(details)

    def _handle_schedule_call(
        self, user_message: str, session: SessionRecord
    ) -> tuple[str, WorkflowState, SessionRecord]:
        """Handle schedule call task.

        Args:
            user_message: The user's input.
            session: Current session record.

        Returns:
            Tuple of (reply, next state, updated session).
        """
        try:
            dealer_id = self.session_service.require_selected_dealer(session)
            car_id = self.session_service.require_selected_car(session)

            outcome, next_state = self.schedule_call.execute(
                user_message,
                dealer_id,
                car_id,
                session.session_id,
                session.scheduling_context,
            )

            # Carry partial date/time across turns; cleared once created.
            session = self.session_service.set_scheduling_context(session, dict(outcome.context))

            if outcome.status == "created" and outcome.record is not None:
                logger.info(
                    "schedule %s created for session %s",
                    outcome.record.schedule_id,
                    session.session_id,
                )
                return outcome.reply, next_state, session

            # Everything else is a question: missing, ambiguous, unreadable,
            # past, or a persistence failure.
            question = ClarificationMessage(
                reply=outcome.question,
                missing_fields=outcome.missing_fields,
            )
            return question.reply, next_state, session

        except DomainError as e:
            # No dealer/car selected: stay put and ask the user to pick a car.
            return str(e), WorkflowState(session.workflow_state), session

        except Exception as e:
            logger.error(f"Schedule call failed: {str(e)}")
            return (
                f"Failed to schedule call: {str(e)}",
                WorkflowState.AWAITING_DATETIME,
                session,
            )
