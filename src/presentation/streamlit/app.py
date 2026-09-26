"""Streamlit chat interface.

Interactive UI for the car dealer chatbot.
"""

from __future__ import annotations

import logging
import uuid

import requests
import streamlit as st

logger = logging.getLogger(__name__)

# Configure Streamlit page
st.set_page_config(
    page_title="Car Dealer Chatbot",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# API base URL (configurable via environment)
API_BASE_URL = st.secrets.get("API_BASE_URL", "http://localhost:8000")


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


def check_api_health() -> bool:
    """Check if API is healthy.

    Returns:
        True if API is accessible, False otherwise.
    """
    try:
        response = requests.get(f"{API_BASE_URL}/api/health", timeout=2)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to connect to API: {str(e)}")
        return False


def send_message(user_input: str) -> tuple[str, str]:
    """Send a message to the chat API.

    Args:
        user_input: The user's message.

    Returns:
        Tuple of (reply, workflow_state) or ("Error message", "ERROR") on failure.
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/chat",
            json={
                "session_id": st.session_state.session_id,
                "message": user_input,
                "user_id": None,
            },
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            return data["reply"], data["workflow_state"]
        else:
            error_detail = response.json().get("detail", "Unknown error")
            return f"Error: {error_detail}", "ERROR"

    except requests.exceptions.ConnectionError:
        return "Unable to connect to API. Is the server running?", "ERROR"
    except requests.exceptions.Timeout:
        return "API request timed out. Please try again.", "ERROR"
    except Exception as e:
        logger.error(f"Failed to send message: {str(e)}")
        return f"Error: {str(e)}", "ERROR"


def reset_session() -> None:
    """Reset the current session."""
    try:
        requests.delete(f"{API_BASE_URL}/api/sessions/{st.session_state.session_id}")
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.workflow_state = "START"
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
        st.info("Start the server with: `uvicorn src.presentation.api.main:app --reload`")
        return

    # Display message history
    st.markdown("### Conversation")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Input area
    st.markdown("---")
    user_input = st.chat_input("Type your message here...")

    if user_input:
        # Display user message
        with st.chat_message("user"):
            st.markdown(user_input)

        # Add to history
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Get response
        with st.spinner("Thinking..."):
            reply, new_state = send_message(user_input)

        # Display assistant response
        with st.chat_message("assistant"):
            st.markdown(reply)

        # Add to history
        st.session_state.messages.append({"role": "assistant", "content": reply})

        # Update state
        st.session_state.workflow_state = new_state

        # Rerun to refresh UI
        st.rerun()


if __name__ == "__main__":
    main()
