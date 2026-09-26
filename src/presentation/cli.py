"""Command-line interface for the car dealer chatbot."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from config.logging import configure_logging
from config.settings import Settings
from DTO.inputs.chat import ChatRequest
from presentation.api.dependencies import AppDependencies

logger = logging.getLogger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument vector.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Chat with the car dealer assistant.")
    parser.add_argument("--user-id", help="Optional user identifier to associate with the session.")
    parser.add_argument("--session-id", help="Resume an existing session id.")
    return parser.parse_args(argv)


def _print_welcome() -> None:
    """Print the startup banner and quick help."""
    print("Car Dealer Chatbot CLI")
    print("Type your message normally. Special commands: /reset, /help, /quit")
    print("Example: I want a BMW 3 Series 320i 2021")


def _print_response(reply: str, workflow_state: str, suggested_actions: list[str]) -> None:
    """Render a chat response to the terminal."""
    print(f"\nBot [{workflow_state}]: {reply}")
    if suggested_actions:
        print("Suggested actions:")
        for action in suggested_actions:
            print(f"- {action}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the interactive CLI chat loop.

    Args:
        argv: Optional argument vector.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    settings = Settings()
    configure_logging(
        level=settings.app_settings.log_level,
        log_file=settings.app_settings.log_file,
    )

    deps = AppDependencies.get_instance(settings)
    session_id = args.session_id
    _print_welcome()

    while True:
        try:
            raw = input("\nYou: ")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            return 0

        message = raw.strip()
        if not message:
            print("Please enter a non-empty message.")
            continue

        lowered = message.lower()
        if lowered in {"/quit", "quit", "exit"}:
            print("Goodbye.")
            return 0
        if lowered in {"/help", "help"}:
            _print_welcome()
            continue
        if lowered == "/reset":
            if session_id:
                deps.session_store.delete(session_id)
                logger.info("CLI reset session %s", session_id)
            session_id = None
            print("Session reset. Starting a fresh conversation.")
            continue

        response = deps.chat_service.chat(
            ChatRequest(session_id=session_id, message=message, user_id=args.user_id)
        )
        session_id = response.session_id
        _print_response(response.reply, response.workflow_state, response.suggested_actions)


if __name__ == "__main__":
    raise SystemExit(main())
