"""Conversation prompt template.

Used for contextual conversational turns that do not map to a direct task
(car lookup, dealer details, schedule). The LLM uses the session history and
the list of cars already shown to the user to answer naturally.
"""

from __future__ import annotations


def build_conversation_prompt(
    user_message: str,
    conversation_history: str,
    seen_cars_summary: str,
    current_state: str,
) -> str:
    """Build a prompt for a conversational (non-task) turn.

    Args:
        user_message: The user's raw input.
        conversation_history: Recent messages formatted as "role: content".
        seen_cars_summary: Human-readable list of cars shown this session.
        current_state: Current workflow state string for context.

    Returns:
        The full prompt text sent to the LLM.
    """
    return f"""You are a helpful car dealer chatbot assistant.
The user is asking a conversational question or wants context about what has already happened in this session.

Current conversation state: {current_state}

Cars shown to the user so far this session:
{seen_cars_summary or "None yet."}

Recent conversation:
{conversation_history or "No prior messages."}

User message: "{user_message}"

Answer using only the information shown above.
- If they ask which cars they have seen, list the cars above.
- If they ask for a comparison or suggestion, reason from the cars above only.
- If they ask a general car domain question, answer briefly and helpfully.
- If there is not enough context to answer, politely say so and suggest searching for a car.
- Never invent cars, prices, or dealer information not listed in the context above.
- Keep the response friendly and concise (2–4 sentences).

Respond with JSON only, with a single field: reply."""
