"""Intent extraction prompt template.

This prompt instructs the LLM to classify user input as one of three tasks,
and to never invent a task outside this set. The response is constrained
to the TaskDecision schema.
"""

from __future__ import annotations

from domain.enums.task_type import TaskType
from models.inputs.task import TaskDecision


def build_intent_prompt(user_message: str) -> str:
    """Build the intent extraction prompt.

    Args:
        user_message: The raw user input to classify.

    Returns:
        The full prompt text sent to the LLM.
    """
    return f"""You are a task router for a car dealer chatbot. 
Your job is to classify the user's input into exactly one of three tasks:

1. ITEM_LOOKUP: The user wants to search for or identify a car.
   Examples: "I'm looking for a BMW", "What cars do you have?", "Show me a red car"

2. DEALER_DETAILS: The user wants information about a specific dealer.
   Examples: "Tell me about the dealer", "What's the dealer's phone number?", "Where is the dealer located?"

3. SCHEDULE_CALL: The user wants to schedule a call with the dealer.
   Examples: "I want to book a time", "Can we schedule a call for tomorrow?", "When can I call?"

4. UNKNOWN: The user's intent is unclear or not one of the above.
   Examples: "What's the weather?", "Tell me a joke", unclear or ambiguous requests

Classify the following user message. Return your response as JSON with:
- task_type: One of {[t.value for t in TaskType]}
- confidence: A float between 0.0 and 1.0 (1.0 = certain)
- reason: A brief explanation of your classification

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
