"""Data models for conversation context."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class Message:
    """Represents a single message in a conversation."""

    chat_id: int
    user_id: int
    message_text: str
    role: str  # "user" or "assistant"
    timestamp: datetime
    message_id: Optional[int] = None
    raw_json: Optional[str] = None
    reply_to_message_id: Optional[int] = None


@dataclass
class ConversationContext:
    """Context for a conversation including recent messages and metadata."""

    chat_id: int
    user_id: int
    messages: List[Message]
    recent_limit: int = 10

    def format_for_llm(self) -> str:
        """
        Format conversation context for LLM consumption.

        Returns:
            Formatted string with conversation history
        """
        formatted = []
        for msg in self.messages:
            role_label = "User" if msg.role == "user" else "Assistant"
            formatted.append(f"{role_label}: {msg.message_text}")
        return "\n".join(formatted)

    def get_recent_messages(self, limit: Optional[int] = None) -> List[Message]:
        """
        Get recent messages up to limit.

        Args:
            limit: Maximum number of messages to return

        Returns:
            List of recent messages
        """
        if limit is None:
            limit = self.recent_limit
        return self.messages[-limit:] if len(self.messages) > limit else self.messages

