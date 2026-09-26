"""Schedule extraction prompt template.

This prompt instructs the LLM to extract date/time/timezone from user input,
keeping the text as raw as possible so ambiguities can be resolved later.
The response is constrained to the ScheduleExtraction schema.
"""

from __future__ import annotations


def build_schedule_extraction_prompt(user_message: str) -> str:
    """Build the schedule extraction prompt.

    Args:
        user_message: The user's raw input about scheduling a call.

    Returns:
        The full prompt text sent to the LLM.
    """
    return f"""You are a schedule information extractor. Your job is to extract date/time details from user input.

Extract the following from the user message if present:
- date_raw: The date mentioned (as written by the user, e.g., "tomorrow", "Friday", "next week", "2024-12-25")
- time_raw: The time mentioned (as written by the user, e.g., "3pm", "15:00", "afternoon", "morning")
- timezone: The timezone mentioned (e.g., "EST", "PST", "UTC"), or null if not mentioned

IMPORTANT:
- Keep the extracted text as raw and natural as possible.
- If a field is NOT mentioned or unclear, return null for that field, NEVER guess or assume.
- Do NOT parse dates/times into standard formats (we will do that separately).
- Do NOT invent scheduling information.

User message: "{user_message}"

Respond with JSON only, with fields: date_raw, time_raw, timezone (all nullable strings)."""
