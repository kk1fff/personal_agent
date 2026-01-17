"""Conversation context manager."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from .conversation_db import ConversationDB
from .models import ConversationContext, Message


class ConversationContextManager:
    """Manages conversation context retrieval and storage."""

    def __init__(
        self,
        db: ConversationDB,
        default_limit: int = 10,
        time_gap_threshold_minutes: int = 60,
        lookback_limit: int = 25,
    ):
        """
        Initialize context manager.

        Args:
            db: ConversationDB instance
            default_limit: Default number of recent messages to retrieve
            time_gap_threshold_minutes: Time gap (minutes) that defines session boundary
            lookback_limit: Maximum messages to inspect when clustering
        """
        self.db = db
        self.default_limit = default_limit
        self.time_gap_threshold = timedelta(minutes=time_gap_threshold_minutes)
        self.lookback_limit = lookback_limit

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
        reply_to_message_id: Optional[int] = None,
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
            reply_to_message_id: Optional ID of message this is replying to
        """
        await self.db.save_message(
            chat_id, user_id, message, role, message_id, raw_json, reply_to_message_id
        )

    async def get_recent_messages(
        self, chat_id: int, limit: Optional[int] = None
    ) -> List[Message]:
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

    async def get_message_by_id(
        self, chat_id: int, message_id: int
    ) -> Optional[Message]:
        """
        Get a specific message by its Telegram message ID.

        Args:
            chat_id: Telegram chat ID
            message_id: Telegram message ID

        Returns:
            Message object or None if not found
        """
        return await self.db.get_message_by_id(chat_id, message_id)

    async def get_smart_context(
        self,
        chat_id: int,
        user_id: int,
        current_timestamp: Optional[datetime] = None,
    ) -> Tuple[ConversationContext, int]:
        """
        Get conversation context using time-gap clustering.

        Retrieves messages from the "current session" by finding
        where the time gap between consecutive messages exceeds
        the threshold.

        Args:
            chat_id: Telegram chat ID
            user_id: Telegram user ID
            current_timestamp: Reference timestamp (defaults to now UTC)

        Returns:
            Tuple of (ConversationContext, session_message_count)
        """
        if current_timestamp is None:
            current_timestamp = datetime.now(timezone.utc)

        # Get messages in reverse chronological order (newest first)
        messages = await self.db.get_messages_for_clustering(
            chat_id, self.lookback_limit
        )

        if not messages:
            return ConversationContext(
                chat_id=chat_id,
                user_id=user_id,
                messages=[],
            ), 0

        # Find session boundary using time-gap clustering
        session_messages = []
        prev_timestamp = current_timestamp

        for msg in messages:
            # Make msg.timestamp timezone-aware if it's naive
            msg_timestamp = msg.timestamp
            if msg_timestamp.tzinfo is None:
                msg_timestamp = msg_timestamp.replace(tzinfo=timezone.utc)

            # Calculate gap from previous message
            gap = prev_timestamp - msg_timestamp

            if gap > self.time_gap_threshold:
                # Found session boundary - messages before this gap
                # are from a different session
                break

            session_messages.append(msg)
            prev_timestamp = msg_timestamp

        # Reverse to chronological order (oldest first)
        session_messages.reverse()

        return ConversationContext(
            chat_id=chat_id,
            user_id=user_id,
            messages=session_messages,
            recent_limit=len(session_messages),
        ), len(session_messages)
