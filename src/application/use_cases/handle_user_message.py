"""Handle user message use case.

Orchestrates a full chat turn: load session, select task, dispatch, save session.
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
from DTO.outputs.chat import ChatResponse
from models.outputs.session import SessionRecord
from ports.llm import LLMPort
from ports.repositories.car_repository import CarRepository
from ports.repositories.dealer_repository import DealerRepository
from ports.session_store import SessionStore

logger = logging.getLogger(__name__)


class HandleUserMessageUseCase:
    """Orchestrate a full chat turn."""

    def __init__(
        self,
        session_store: SessionStore,
        llm: LLMPort,
        car_repo: CarRepository,
        dealer_repo: DealerRepository,
    ) -> None:
        """Initialize with all dependencies.

        Args:
            session_store: SessionStore for session persistence.
            llm: LLMPort for LLM calls.
            car_repo: CarRepository for car search.
            dealer_repo: DealerRepository for dealer lookup.
        """
        self.session_service = SessionService(session_store)
        self.load_session = LoadSessionUseCase(session_store)
        self.save_session = SaveSessionUseCase(session_store)
        self.select_task = SelectTaskUseCase(llm)
        self.lookup_car = LookupCarUseCase(llm, car_repo, dealer_repo)
        self.get_dealer_details = GetDealerDetailsUseCase(dealer_repo)
        self.schedule_call = ScheduleCallUseCase(llm)

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

            if task_type == TaskType.ITEM_LOOKUP:
                reply, next_state, session = self._handle_item_lookup(request.message, session)

            elif task_type == TaskType.DEALER_DETAILS:
                reply, next_state = self._handle_dealer_details(session)

            elif task_type == TaskType.SCHEDULE_CALL:
                reply, next_state = self._handle_schedule_call(request.message, session)

            else:
                reply = "I didn't understand that. Please try asking me to find a car, show dealer details, or schedule a call."

            # Step 5: Update session
            session = self.session_service.advance_workflow(session, next_state)
            session = self.session_service.append_message(session, "assistant", reply)

            # Step 6: Persist
            self.session_service.persist(session)

            # Step 7: Build response
            return ChatResponse(
                session_id=session.session_id,
                reply=reply,
                workflow_state=session.workflow_state,
                suggested_actions=[],
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
    ) -> tuple[str, WorkflowState, SessionRecord]:
        """Handle car lookup task.

        Args:
            user_message: The user's input.
            session: Current session record.

        Returns:
            Tuple of (reply, next state, updated session).
        """
        try:
            result, dealer, next_state = self.lookup_car.execute(user_message)

            if result.status == "found":
                car = result.cars[0]
                session = self.session_service.set_selected_car(session, car.car_id)
                if dealer:
                    session = self.session_service.set_selected_dealer(session, dealer.dealer_id)
                reply = f"Found {car.make} {car.model}. Would you like dealer details or to schedule a call?"

            elif result.status == "multiple":
                reply = "I found multiple cars. Which one interests you? " + ", ".join(
                    [f"{c.make} {c.model}" for c in result.candidates]
                )

            else:
                reply = "I couldn't find a car matching that description. Can you try a different search?"

            return reply, next_state, session

        except Exception as e:
            logger.error(f"Item lookup failed: {str(e)}")
            return f"Car search failed: {str(e)}", WorkflowState.AWAITING_CAR, session

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

            if dealer:
                reply = (
                    f"Dealer: {dealer.dealer_name}\n"
                    f"City: {dealer.city}\n"
                    f"Phone: {dealer.phone}\n"
                    f"Email: {dealer.email}\n"
                    f"Rating: {dealer.rating}"
                )
            else:
                reply = "Could not retrieve dealer details."

            return reply, next_state

        except DomainError as e:
            return str(e), WorkflowState.AWAITING_ACTION

        except Exception as e:
            logger.error(f"Dealer details failed: {str(e)}")
            return f"Failed to get dealer details: {str(e)}", WorkflowState.AWAITING_ACTION

    def _handle_schedule_call(
        self, user_message: str, session: SessionRecord
    ) -> tuple[str, WorkflowState]:
        """Handle schedule call task.

        Args:
            user_message: The user's input.
            session: Current session record.

        Returns:
            Tuple of (reply, next state).
        """
        try:
            dealer_id = self.session_service.require_selected_dealer(session)
            car_id = self.session_service.require_selected_car(session)

            schedule, next_state = self.schedule_call.execute(
                user_message, dealer_id, car_id, session.session_id
            )

            if schedule:
                reply = (
                    f"Call scheduled for {schedule.scheduled_for} "
                    f"({schedule.timezone}). We'll be in touch!"
                )
            else:
                reply = "Could not schedule the call. Please try again."

            return reply, next_state

        except DomainError as e:
            return str(e), WorkflowState.AWAITING_ACTION

        except Exception as e:
            logger.error(f"Schedule call failed: {str(e)}")
            return f"Failed to schedule call: {str(e)}", WorkflowState.AWAITING_DATETIME
