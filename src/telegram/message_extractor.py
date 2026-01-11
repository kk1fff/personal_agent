"""Message extraction and validation from Telegram."""

import json
import logging
from dataclasses import dataclass
from typing import List, Optional

from ..config.config_schema import AppConfig

logger = logging.getLogger(__name__)


@dataclass
class ExtractedMessage:
    """Extracted and validated message from Telegram."""

    chat_id: int
    user_id: int
    message_text: str
    message_id: Optional[int] = None
    username: Optional[str] = None
    is_command: bool = False
    is_mentioned: bool = False
    raw_json: Optional[str] = None


class MessageExtractor:
    """Extracts and validates messages from Telegram."""

    def __init__(self, config: AppConfig):
        """
        Initialize message extractor.

        Args:
            config: Application configuration
        """
        self.config = config
        self.allowed_chat_ids = {
            conv.chat_id for conv in config.allowed_conversations
        }
        self.allowed_user_ids = {user.user_id for user in config.allowed_users}
        self.bot_username: Optional[str] = None

    def set_bot_username(self, username: str) -> None:
        """
        Set bot username for mention detection.

        Args:
            username: Bot username (with or without @ prefix)
        """
        self.bot_username = username.lower().lstrip('@')
        logger.info(f"Bot username set to: @{self.bot_username}")

    def is_bot_mentioned(self, message: dict) -> bool:
        """
        Check if bot is mentioned in message using Telegram entities.

        This method ONLY checks if bot is mentioned, it does NOT filter messages.
        All messages are stored; mention status is used to decide whether to respond.

        Args:
            message: Message dictionary from Telegram update

        Returns:
            True if bot is mentioned, False otherwise
        """
        # If feature disabled, always return True (respond to all)
        if not self.config.telegram.require_mention:
            return True

        # Safety: if bot username not set, return True
        if not self.bot_username:
            logger.warning("Bot username not set, treating as mentioned")
            return True

        # Get entities and text
        entities = message.get("entities", [])
        text = message.get("text", "")

        # Check each entity for bot mention
        for entity in entities:
            entity_type = entity.get("type")

            if entity_type == "mention":
                # Extract mention text using offset and length
                offset = entity.get("offset", 0)
                length = entity.get("length", 0)
                mention_text = text[offset:offset+length]
                mentioned_username = mention_text.lstrip('@').lower()

                if mentioned_username == self.bot_username.lower():
                    return True

        return False

    def extract(self, update: dict) -> Optional[ExtractedMessage]:
        """
        Extract message from Telegram update.

        Args:
            update: Telegram update dictionary

        Returns:
            ExtractedMessage if valid, None otherwise
        """
        # Handle message updates
        if "message" not in update:
            return None

        message = update["message"]
        chat = message.get("chat", {})
        from_user = message.get("from", {})

        chat_id = chat.get("id")
        user_id = from_user.get("id")
        message_text = message.get("text", "")
        message_id = message.get("message_id")
        username = from_user.get("username")

        if not message_text or not chat_id or not user_id:
            return None

        # Check if conversation is allowed
        if not self.is_allowed_conversation(chat_id):
            return None

        # Check if user is allowed (if user restrictions are configured)
        if self.allowed_user_ids and not self.is_allowed_user(user_id):
            return None

        # Check if it's a command (starts with /)
        is_command = message_text.startswith("/")

        # Check if bot is mentioned (but DON'T filter)
        is_mentioned = self.is_bot_mentioned(message)

        # Store raw JSON
        raw_json = json.dumps(update)

        return ExtractedMessage(
            chat_id=chat_id,
            user_id=user_id,
            message_text=message_text,
            message_id=message_id,
            username=username,
            is_command=is_command,
            is_mentioned=is_mentioned,
            raw_json=raw_json,
        )

    def is_allowed_conversation(self, chat_id: int) -> bool:
        """
        Check if conversation ID is allowed.

        Args:
            chat_id: Telegram chat ID

        Returns:
            True if allowed
        """
        # If no restrictions, allow all
        if not self.allowed_chat_ids:
            return True

        return chat_id in self.allowed_chat_ids

    def is_allowed_user(self, user_id: int) -> bool:
        """
        Check if user ID is allowed.

        Args:
            user_id: Telegram user ID

        Returns:
            True if allowed
        """
        # If no restrictions, allow all
        if not self.allowed_user_ids:
            return True

        return user_id in self.allowed_user_ids

