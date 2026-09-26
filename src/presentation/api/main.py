"""FastAPI application setup.

Initializes the FastAPI app with routes, exception handlers, and middleware.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.settings import Settings
from domain.exceptions import DomainError
from presentation.api.dependencies import AppDependencies
from presentation.api.error_mappers import domain_error_to_http
from presentation.api.routes.chat import router as chat_router

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI app.

    Args:
        settings: Optional settings override.

    Returns:
        The configured FastAPI application.
    """
    if settings is None:
        settings = Settings()

    app = FastAPI(
        title="Car Dealer Chatbot API",
        description="Chat API for car dealer interactions",
        version="0.1.0",
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize dependencies (fail fast on config error)
    try:
        AppDependencies.get_instance(settings)
        logger.info("Dependencies initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize dependencies: {str(e)}")
        raise

    # Add exception handlers
    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        """Handle domain exceptions."""
        http_exc = domain_error_to_http(exc)
        return JSONResponse(
            status_code=http_exc.status_code,
            content={"detail": http_exc.detail},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected exceptions."""
        logger.error(f"Unexpected exception: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred."},
        )

    # Include routers
    app.include_router(chat_router)

    # Root endpoint
    @app.get("/")
    async def root() -> dict[str, str]:
        """Root endpoint."""
        return {
            "message": "Car Dealer Chatbot API",
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


# Create the app instance
app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
