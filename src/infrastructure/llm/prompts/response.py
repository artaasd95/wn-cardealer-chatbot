"""Response wording prompt template.

Every reply the bot produces for a completed task goes through this prompt.
It only ever receives data the application already holds (what the repository
returned, flattened by the application layer), never catalog access, so the
LLM restates facts instead of inventing cars, dealers or times.
"""

from __future__ import annotations


def build_response_prompt(task_summary: str, data_summary: str) -> str:
    """Build the response wording prompt.

    Args:
        task_summary: A brief summary of what the task accomplished.
        data_summary: A summary of the data the task produced, built by the
            application from its own models/DTOs.

    Returns:
        The full prompt text sent to the LLM for response generation.
    """
    return f"""You are a friendly car dealer chatbot assistant.

Task result: {task_summary}

Data: {data_summary}

Write a natural, helpful response to the user that:
1. Acknowledges what they asked for
2. Provides the relevant information or next steps
3. Is friendly and concise (2-3 sentences)
4. Never includes technical jargon or internal details
5. Never invents facts that are not stated in the Data above

Respond with JSON only, with a single field: reply."""
