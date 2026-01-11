"""Conversation context manager."""

from typing import Optional

from .conversation_db import ConversationDB
from .models import ConversationContext, Message


class ConversationContextManager:
    """Manages conversation context retrieval and storage."""

    def __init__(self, db: ConversationDB, default_limit: int = 10):
        """
        Initialize context manager.

        Args:
            db: ConversationDB instance
            default_limit: Default number of recent messages to retrieve
        """
        self.db = db
        self.default_limit = default_limit

    async def get_context(
        self, chat_id: int, user_id: int, limit: Optional[int] = None
    ) -> ConversationContext:
        """
        Get conversation context for a chat.

        Args:
            chat_id: Telegram chat ID
            user_id: Telegram user ID
            limit: Maximum number of recent messages to include

        Returns:
            ConversationContext with recent messages
        """
        if limit is None:
            limit = self.default_limit

        messages = await self.db.get_recent_messages(chat_id, limit)

        return ConversationContext(
            chat_id=chat_id,
            user_id=user_id,
            messages=messages,
            recent_limit=limit,
        )

    async def save_message(
        self,
        chat_id: int,
        user_id: int,
        message: str,
        role: str,
        message_id: Optional[int] = None,
        raw_json: Optional[str] = None,
    ) -> None:
        """
        Save a message to the conversation database.

        Args:
            chat_id: Telegram chat ID
            user_id: Telegram user ID
            message: Message content
            role: Message role ("user" or "assistant")
            message_id: Optional Telegram message ID
            raw_json: Optional raw JSON from Telegram update
        """
        await self.db.save_message(chat_id, user_id, message, role, message_id, raw_json)

    async def get_recent_messages(
        self, chat_id: int, limit: Optional[int] = None
    ) -> list[Message]:
        """
        Get recent messages for a chat.

        Args:
            chat_id: Telegram chat ID
            limit: Maximum number of messages to retrieve

        Returns:
            List of recent messages
        """
        if limit is None:
            limit = self.default_limit

        return await self.db.get_recent_messages(chat_id, limit)

