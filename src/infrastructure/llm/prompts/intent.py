"""Intent extraction prompt template.

This prompt instructs the LLM to classify user input as one of three tasks,
and to never invent a task outside this set. The response is constrained
to the TaskDecision schema.
"""

from __future__ import annotations

from domain.enums.task_type import TaskType
from models.inputs.task import TaskDecision


def build_intent_prompt(user_message: str, conversation_history: str = "") -> str:
    """Build the intent extraction prompt.

    Args:
        user_message: The raw user input to classify.
        conversation_history: Optional recent conversation context.

    Returns:
        The full prompt text sent to the LLM.
    """
    history_block = ""
    if conversation_history:
        history_block = f"""

Recent conversation:
{conversation_history}
"""
    return f"""You are a task router for a car dealer chatbot.
Classify the user's input into exactly one of these tasks:

1. GREETING: A social greeting or casual opener with no task intent.
   Examples: "hi", "hello", "good morning", "how are you", "hey there"

2. ITEM_LOOKUP: The user wants to search for or find a specific car.
   Examples: "I'm looking for a BMW", "What cars do you have?", "Show me a Honda Civic 2021"

3. DEALER_DETAILS: The user wants information about a dealer.
   Examples: "Tell me about the dealer", "What's the dealer's phone number?", "Where is the dealer?"

4. SCHEDULE_CALL: The user wants to schedule a call with a dealer.
   Examples: "I want to book a time", "Can we schedule a call for tomorrow?", "When can I call?"

5. CONVERSATION: A contextual question about cars or dealers already seen, or advice about options.
   Examples: "what cars did I see?", "which is cheaper?", "what do you suggest?",
             "tell me more about that car", "compare those options", "what have we discussed?"

6. UNKNOWN: Completely unrelated or ambiguous input.
   Examples: "What's the weather?", "Tell me a joke"

Classify this message. Return JSON with:
- task_type: One of {[t.value for t in TaskType]}
- confidence: Float 0.0–1.0 (1.0 = certain)
- reason: Brief explanation
{history_block}
User message: "{user_message}"

Respond with JSON only."""


def parse_task_decision(decision: TaskDecision) -> TaskType:
    """Parse a TaskDecision into a TaskType.

    Args:
        decision: The LLM's structured response.

    Returns:
        The classified task type, or UNKNOWN if confidence is too low.
    """
    if decision.confidence < 0.5:
        return TaskType.UNKNOWN

    try:
        return TaskType(decision.task_type)
    except ValueError:
        return TaskType.UNKNOWN
