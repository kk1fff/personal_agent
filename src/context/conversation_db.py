"""SQLite database for conversation storage."""

import logging
import aiosqlite
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .models import Message

logger = logging.getLogger(__name__)


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

    async def _run_migrations(self) -> None:
        """Run database migrations for schema updates."""
        async with aiosqlite.connect(self.db_path) as db:
            # Check if reply_to_message_id column exists
            async with db.execute("PRAGMA table_info(messages)") as cursor:
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]

            # Add reply_to_message_id column if missing
            if "reply_to_message_id" not in column_names:
                logger.info("Running migration: Adding reply_to_message_id column")
                await db.execute(
                    "ALTER TABLE messages ADD COLUMN reply_to_message_id INTEGER"
                )
                await db.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_reply_to_message_id
                    ON messages(reply_to_message_id)
                    """
                )
                await db.commit()
                logger.info("Migration complete: reply_to_message_id column added")

    async def initialize(self) -> None:
        """Initialize database schema."""
        if self._initialized:
            return

        # Ensure directory exists
        db_path_obj = Path(self.db_path)
        db_path_obj.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            # Create table with full schema (for new databases)
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    message_text TEXT NOT NULL,
                    role TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    message_id INTEGER,
                    raw_json TEXT,
                    reply_to_message_id INTEGER
                )
                """
            )
            # Create indexes that don't depend on new columns
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_id_timestamp
                ON messages(chat_id, timestamp)
                """
            )
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_message_id
                ON messages(message_id)
                """
            )
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_id
                ON messages(chat_id)
                """
            )
            await db.commit()

        # Run migrations for existing databases (adds reply_to_message_id column if missing)
        await self._run_migrations()

        # Create index on reply_to_message_id AFTER migration ensures column exists
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_reply_to_message_id
                ON messages(reply_to_message_id)
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
        raw_json: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
    ) -> None:
        """
        Save a message to the database.

        Args:
            chat_id: Telegram chat ID
            user_id: Telegram user ID
            message_text: Message content
            role: Message role ("user" or "assistant")
            message_id: Optional Telegram message ID
            raw_json: Optional raw JSON from Telegram update
            reply_to_message_id: Optional ID of message this is replying to
        """
        await self.initialize()

        timestamp = datetime.utcnow().isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO messages (chat_id, user_id, message_text, role, timestamp, message_id, raw_json, reply_to_message_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (chat_id, user_id, message_text, role, timestamp, message_id, raw_json, reply_to_message_id),
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
                SELECT * FROM (
                    SELECT id, chat_id, user_id, message_text, role, timestamp, message_id, raw_json, reply_to_message_id
                    FROM messages
                    WHERE chat_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ) ORDER BY timestamp ASC
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
                    raw_json=row["raw_json"],
                    reply_to_message_id=row["reply_to_message_id"],
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
                SELECT id, chat_id, user_id, message_text, role, timestamp, message_id, raw_json, reply_to_message_id
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
                    raw_json=row["raw_json"],
                    reply_to_message_id=row["reply_to_message_id"],
                )
            )

        return messages

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
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT id, chat_id, user_id, message_text, role, timestamp, message_id, raw_json, reply_to_message_id
                FROM messages
                WHERE chat_id = ? AND message_id = ?
                """,
                (chat_id, message_id),
            ) as cursor:
                row = await cursor.fetchone()

        if row:
            return Message(
                chat_id=row["chat_id"],
                user_id=row["user_id"],
                message_text=row["message_text"],
                role=row["role"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                message_id=row["message_id"],
                raw_json=row["raw_json"],
                reply_to_message_id=row["reply_to_message_id"],
            )
        return None

    async def get_messages_for_clustering(
        self, chat_id: int, limit: int = 25
    ) -> List[Message]:
        """
        Get recent messages for time-gap clustering.

        Returns messages in reverse chronological order (newest first)
        for easier gap calculation.

        Args:
            chat_id: Telegram chat ID
            limit: Maximum messages to inspect

        Returns:
            List of Message objects, newest first
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT id, chat_id, user_id, message_text, role, timestamp, message_id, raw_json, reply_to_message_id
                FROM messages
                WHERE chat_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (chat_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()

        return [
            Message(
                chat_id=row["chat_id"],
                user_id=row["user_id"],
                message_text=row["message_text"],
                role=row["role"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                message_id=row["message_id"],
                raw_json=row["raw_json"],
                reply_to_message_id=row["reply_to_message_id"],
            )
            for row in rows
        ]

