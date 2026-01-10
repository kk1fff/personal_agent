"""Tests for conversation database."""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime

from src.context.conversation_db import ConversationDB
from src.context.models import Message


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    db_path = "test_conversations.db"
    db = ConversationDB(db_path)
    yield db
    # Cleanup
    if Path(db_path).exists():
        Path(db_path).unlink()


@pytest.mark.asyncio
async def test_initialize_database(temp_db):
    """Test database initialization."""
    await temp_db.initialize()
    # Should not raise an exception
    assert True


@pytest.mark.asyncio
async def test_save_message(temp_db):
    """Test saving a message."""
    await temp_db.initialize()

    await temp_db.save_message(
        chat_id=123,
        user_id=456,
        message_text="Hello, world!",
        role="user",
        message_id=789,
    )

    messages = await temp_db.get_recent_messages(chat_id=123, limit=10)
    assert len(messages) == 1
    assert messages[0].message_text == "Hello, world!"
    assert messages[0].role == "user"
    assert messages[0].chat_id == 123
    assert messages[0].user_id == 456


@pytest.mark.asyncio
async def test_get_recent_messages(temp_db):
    """Test retrieving recent messages."""
    await temp_db.initialize()

    # Save multiple messages
    for i in range(5):
        await temp_db.save_message(
            chat_id=123,
            user_id=456,
            message_text=f"Message {i}",
            role="user" if i % 2 == 0 else "assistant",
        )

    messages = await temp_db.get_recent_messages(chat_id=123, limit=3)
    assert len(messages) == 3
    # Should be ordered by timestamp (oldest first)
    assert messages[0].message_text == "Message 0"


@pytest.mark.asyncio
async def test_get_all_messages(temp_db):
    """Test retrieving all messages for a chat."""
    await temp_db.initialize()

    # Save messages to different chats
    await temp_db.save_message(chat_id=123, user_id=456, message_text="Chat 1", role="user")
    await temp_db.save_message(chat_id=456, user_id=456, message_text="Chat 2", role="user")
    await temp_db.save_message(chat_id=123, user_id=456, message_text="Chat 1 again", role="user")

    messages = await temp_db.get_all_messages(chat_id=123)
    assert len(messages) == 2
    assert all(msg.chat_id == 123 for msg in messages)

