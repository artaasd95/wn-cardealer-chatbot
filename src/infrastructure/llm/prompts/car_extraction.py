"""Car extraction prompt template.

This prompt instructs the LLM to extract make/model/variant from user input,
and to return None/null rather than guess when information is missing.
The response is constrained to the CarExtraction schema.
"""

from __future__ import annotations


def build_car_extraction_prompt(
    user_message: str,
    conversation_context: str | None = None,
) -> str:
    """Build the car extraction prompt.

    Args:
        user_message: The user's raw input about a car.
        conversation_context: Optional recent conversation to help the model
            resolve omitted fields during a clarification turn.

    Returns:
        The full prompt text sent to the LLM.
    """
    context_block = ""
    if conversation_context:
        context_block = (
            "\nRecent conversation context (use this only to resolve omitted car fields "
            "from the current clarification; do not invent anything beyond it):\n"
            f"{conversation_context}\n"
        )

    return f"""You are a car information extractor. Your job is to extract car details from user input.

Extract the following from the user message if present:
- make: The car manufacturer (e.g., "BMW", "Toyota", "Mercedes-Benz")
- model: The car model (e.g., "3 Series", "Camry", "C-Class")
- variant: The specific variant or trim (e.g., "M340i", "LE", "AMG")
- year_from: Earliest year the user might want (e.g., 2020)
- year_to: Latest year the user might want (e.g., 2024)

IMPORTANT:
- If a field is NOT mentioned or unclear, return null for that field, NEVER guess.
- Do NOT invent car details.
- Be case-insensitive in your extraction.
- Return year values as integers, or null if not mentioned.
- If the current user message is only a clarification (for example just a variant or year),
  you may use the recent conversation context to recover the omitted make/model.

User message: "{user_message}"
{context_block}

Respond with JSON only, with fields: make, model, variant, year_from, year_to (all nullable strings/ints)."""


def normalize_make(make: str | None) -> str | None:
    """Normalize a car make string.

    Args:
        make: The raw make string from the LLM.

    Returns:
        Normalized make string, or None if input is None.
    """
    if not make:
        return None
    return make.strip().lower()


def normalize_model(model: str | None) -> str | None:
    """Normalize a car model string.

    Args:
        model: The raw model string from the LLM.

    Returns:
        Normalized model string, or None if input is None.
    """
    if not model:
        return None
    return model.strip().lower()


def normalize_variant(variant: str | None) -> str | None:
    """Normalize a car variant string.

    Args:
        variant: The raw variant string from the LLM.

    Returns:
        Normalized variant string, or None if input is None.
    """
    if not variant:
        return None
    return variant.strip().lower()
