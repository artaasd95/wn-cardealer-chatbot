"""Streamlit chat interface.

Interactive UI for the car dealer chatbot.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from urllib.parse import urlunsplit

import requests
import streamlit as st

from config.logging import configure_logging
from config.settings import AppSettings

_app_settings = AppSettings()
configure_logging(level=_app_settings.log_level, log_file=_app_settings.log_file)

logger = logging.getLogger(__name__)

# Use a requests Session that ignores system proxy environment variables so
# the UI connects directly to the local API even when a dev machine has a
# proxy (for example a local debugging proxy) configured.
_requests_session = requests.Session()
_requests_session.trust_env = False

# Configure Streamlit page
st.set_page_config(
    page_title="Car Dealer Chatbot",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _default_api_base_url() -> str:
    """Build the default API origin from shared app settings.

    Returns:
        The local API base URL Streamlit should call by default.
    """
    host = _app_settings.host.strip() or "127.0.0.1"
    if host in {"0.0.0.0", "::", "[::]"}:
        host = "127.0.0.1"
    return urlunsplit(("http", f"{host}:{_app_settings.port}", "", "", ""))


# API base URL: environment first, then secrets.toml, then shared app settings.
DEFAULT_API_BASE_URL = _default_api_base_url()


def resolve_api_base_url() -> str:
    """Resolve the API base URL without ever crashing on a missing secrets file.

    Returns:
        The API base URL to call.
    """
    env_url = os.environ.get("API_BASE_URL", "").strip()
    if env_url:
        return env_url
    try:
        secret_url = str(st.secrets.get("API_BASE_URL", "") or "").strip()
        if secret_url:
            return secret_url
    except Exception as exc:  # no .streamlit/secrets.toml exists at all
        logger.debug("streamlit secrets unavailable: %s", exc)
    return DEFAULT_API_BASE_URL


API_BASE_URL = resolve_api_base_url()


def init_session_state() -> None:
    """Initialize Streamlit session state."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "workflow_state" not in st.session_state:
        st.session_state.workflow_state = "START"
    if "api_connected" not in st.session_state:
        st.session_state.api_connected = False
    if "suggested_actions" not in st.session_state:
        st.session_state.suggested_actions = []


def check_api_health() -> bool:
    """Check if API is healthy.

    Returns:
        True if API is accessible, False otherwise.
    """
    max_attempts = 6
    timeout = 2
    delay = 0.5
    for attempt in range(1, max_attempts + 1):
        try:
            response = _requests_session.get(f"{API_BASE_URL}/api/health", timeout=timeout)
            if response.status_code == 200:
                return True
            logger.debug("API health returned status %s", response.status_code)
        except Exception as e:
            logger.debug("API health check attempt %d/%d failed: %s", attempt, max_attempts, e)

        if attempt < max_attempts:
            time.sleep(delay)
            delay = min(delay * 2, 5)

    logger.error("Failed to connect to API after %d attempts", max_attempts)
    return False


def send_message(user_input: str) -> tuple[str, str, list[str]]:
    """Send a message to the chat API.

    Args:
        user_input: The user's message.

    Returns:
        Tuple of (reply, workflow_state, suggested_actions); on failure the
        actions list is empty.
    """
    try:
        # Configurable timeout to allow the backend to complete LLM-backed turns.
        # A single turn may call the LLM up to 3 times, so this must exceed
        # LLM_TIMEOUT_SECONDS.  Set APP_REQUEST_TIMEOUT_SECONDS in .env.
        response = _requests_session.post(
            f"{API_BASE_URL}/api/chat",
            json={
                "session_id": st.session_state.session_id,
                "message": user_input,
                "user_id": None,
            },
            timeout=_app_settings.request_timeout_seconds,
        )

        if response.status_code == 200:
            data = response.json()
            actions = data.get("suggested_actions") or []
            return data["reply"], data["workflow_state"], list(actions)

        try:
            error_detail = response.json().get("detail", "Unknown error")
        except Exception:
            error_detail = response.text or "Unknown error"
        return f"Error: {error_detail}", "ERROR", []

    except requests.exceptions.ConnectionError:
        return "Unable to connect to API. Is the server running?", "ERROR", []
    except requests.exceptions.Timeout:
        return (
            "API request timed out. The backend may be busy — please wait a moment and try again.",
            "ERROR",
            [],
        )
    except Exception as e:
        logger.error(f"Failed to send message: {str(e)}")
        return f"Error: {str(e)}", "ERROR", []


def reset_session() -> None:
    """Reset the current session."""
    try:
        _requests_session.delete(f"{API_BASE_URL}/api/sessions/{st.session_state.session_id}")
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.workflow_state = "START"
        st.session_state.suggested_actions = []
        st.success("Session reset. Starting fresh!")
    except Exception as e:
        st.error(f"Failed to reset session: {str(e)}")


def main() -> None:
    """Main Streamlit app."""
    init_session_state()

    # Header
    st.title("🚗 Car Dealer Chatbot")
    st.markdown("Find cars, get dealer details, or schedule a call. Type naturally and I'll help!")

    # Sidebar
    with st.sidebar:
        st.header("Session")
        st.text(f"ID: {st.session_state.session_id[:8]}...")
        st.text(f"State: {st.session_state.workflow_state}")

        if st.button("🔄 Reset Session"):
            reset_session()
            st.rerun()

        st.divider()

        # API health
        if check_api_health():
            st.success("✓ API connected")
            st.session_state.api_connected = True
        else:
            st.error("✗ API offline")
            st.session_state.api_connected = False

        st.divider()

        st.markdown("### Example queries:")
        st.markdown(
            """
- Find a Honda Civic
- Show me the dealer details
- Schedule a test drive for tomorrow at 2pm
- Reset and start over
            """
        )

    # Main chat area
    if not st.session_state.api_connected:
        st.error(
            "⚠️ **API is not responding.** Make sure the FastAPI server is running on "
            f"{API_BASE_URL}"
        )
        st.info(
            "Start the server with: "
            f"`python -m uvicorn src.presentation.api.main:app --host {_app_settings.host} --port {_app_settings.port}`"
        )
        return

    # Display message history
    st.markdown("### Conversation")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Quick replies: clarification options and next-task suggestions that came
    # back in the response DTO (suggested_actions).
    pending: str | None = None
    actions = st.session_state.suggested_actions or []
    if actions:
        st.markdown("#### Suggested next steps")
        per_row = 3
        for start in range(0, len(actions), per_row):
            cols = st.columns(per_row)
            for offset, action in enumerate(actions[start : start + per_row]):
                if cols[offset].button(action, key=f"sugg_{start + offset}_{action}"):
                    pending = action

    # Input area
    st.markdown("---")
    user_input = st.chat_input("Type your message here...")
    if user_input:
        pending = user_input

    if pending:
        # Display user message
        with st.chat_message("user"):
            st.markdown(pending)

        # Add to history
        st.session_state.messages.append({"role": "user", "content": pending})

        # Get response
        with st.spinner("Thinking..."):
            reply, new_state, suggestions = send_message(pending)

        # Display assistant response
        with st.chat_message("assistant"):
            st.markdown(reply)

        # Add to history
        st.session_state.messages.append({"role": "assistant", "content": reply})

        # Update state and the next-step suggestions from the DTO
        st.session_state.workflow_state = new_state
        st.session_state.suggested_actions = suggestions

        # Rerun to refresh UI
        st.rerun()


if __name__ == "__main__":
    main()
