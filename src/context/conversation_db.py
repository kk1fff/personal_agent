"""SQLite database for conversation storage."""

import aiosqlite
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .models import Message


class ConversationDB:
    """Manages conversation storage in SQLite database."""

    def __init__(self, db_path: str = "data/conversations.db"):
        """
        Initialize conversation database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database schema."""
        if self._initialized:
            return

        # Ensure directory exists
        db_path_obj = Path(self.db_path)
        db_path_obj.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    message_text TEXT NOT NULL,
                    role TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    message_id INTEGER
                )
                """
            )
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_id_timestamp 
                ON messages(chat_id, timestamp)
                """
            )
            await db.commit()

        self._initialized = True

    async def save_message(
        self,
        chat_id: int,
        user_id: int,
        message_text: str,
        role: str,
        message_id: Optional[int] = None,
    ) -> None:
        """
        Save a message to the database.

        Args:
            chat_id: Telegram chat ID
            user_id: Telegram user ID
            message_text: Message content
            role: Message role ("user" or "assistant")
            message_id: Optional Telegram message ID
        """
        await self.initialize()

        timestamp = datetime.utcnow().isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO messages (chat_id, user_id, message_text, role, timestamp, message_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (chat_id, user_id, message_text, role, timestamp, message_id),
            )
            await db.commit()

    async def get_recent_messages(
        self, chat_id: int, limit: int = 10
    ) -> List[Message]:
        """
        Get recent messages for a chat.

        Args:
            chat_id: Telegram chat ID
            limit: Maximum number of messages to retrieve

        Returns:
            List of Message objects, ordered by timestamp (oldest first)
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT id, chat_id, user_id, message_text, role, timestamp, message_id
                FROM messages
                WHERE chat_id = ?
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (chat_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()

        messages = []
        for row in rows:
            messages.append(
                Message(
                    chat_id=row["chat_id"],
                    user_id=row["user_id"],
                    message_text=row["message_text"],
                    role=row["role"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    message_id=row["message_id"],
                )
            )

        return messages

    async def get_all_messages(self, chat_id: int) -> List[Message]:
        """
        Get all messages for a chat.

        Args:
            chat_id: Telegram chat ID

        Returns:
            List of all Message objects for the chat
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT id, chat_id, user_id, message_text, role, timestamp, message_id
                FROM messages
                WHERE chat_id = ?
                ORDER BY timestamp ASC
                """,
                (chat_id,),
            ) as cursor:
                rows = await cursor.fetchall()

        messages = []
        for row in rows:
            messages.append(
                Message(
                    chat_id=row["chat_id"],
                    user_id=row["user_id"],
                    message_text=row["message_text"],
                    role=row["role"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    message_id=row["message_id"],
                )
            )

        return messages

