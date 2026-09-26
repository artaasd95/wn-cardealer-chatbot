"""Chat API routes.

POST /chat - handle user message
GET /health - health check with LLM provider info
DELETE /sessions/{session_id} - delete session
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from domain.exceptions import DomainError
from DTO.inputs.chat import ChatRequest
from DTO.outputs.chat import ChatResponse
from presentation.api.dependencies import AppDependencies, get_dependencies
from presentation.api.error_mappers import domain_error_to_http

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def handle_chat(
    request: ChatRequest,
    deps: AppDependencies = Depends(get_dependencies),
) -> ChatResponse:
    """Handle a user chat message.

    Args:
        request: The incoming chat request.
        deps: Application dependencies.

    Returns:
        The chat response with reply and state.

    Raises:
        HTTPException: On validation or domain errors.
    """
    try:
        response = deps.chat_service.chat(request)
        return response

    except DomainError as e:
        logger.warning(f"Domain error: {str(e)}")
        raise domain_error_to_http(e) from e

    except Exception as e:
        logger.error(f"Unexpected error in /chat: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again.",
        ) from e


@router.get("/health")
async def health_check(
    deps: AppDependencies = Depends(get_dependencies),
) -> dict:
    """Health check endpoint.

    Args:
        deps: Application dependencies.

    Returns:
        Health status with LLM provider info.
    """
    return {
        "status": "healthy",
        "llm_provider": deps.settings.llm_settings.provider,
        "database": "connected",
    }


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    deps: AppDependencies = Depends(get_dependencies),
) -> None:
    """Delete a session.

    Args:
        session_id: The session ID to delete.
        deps: Application dependencies.

    Raises:
        HTTPException: If session not found.
    """
    try:
        deps.session_store.delete(session_id)
        logger.info(f"Session {session_id} deleted")

    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete session.",
        ) from e
