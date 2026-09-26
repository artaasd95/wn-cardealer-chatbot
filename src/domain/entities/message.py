from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

"""Message domain entity."""


@dataclass
class Message:
    """Domain entity representing a single message in conversation history."""

    role: str
    """Role of the speaker: 'user' or 'assistant'."""

    content: str
    """The message text."""

    created_at: datetime = field(default_factory=datetime.utcnow)
    """Timestamp when the message was created."""

    def is_user_message(self) -> bool:
        """Check if this is a user message.

        Returns:
            True if role == 'user'.
        """
        return self.role == "user"

    def is_assistant_message(self) -> bool:
        """Check if this is an assistant message.

        Returns:
            True if role == 'assistant'.
        """
        return self.role == "assistant"

    def length(self) -> int:
        """Return the character length of the message content.

        Returns:
            Length of content string.
        """
        return len(self.content)
