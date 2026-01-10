"""Tests for conversation context manager."""

import pytest
import asyncio
from pathlib import Path

from src.context.conversation_db import ConversationDB
from src.context.context_manager import ConversationContextManager


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    db_path = "test_conversations.db"
    db = ConversationDB(db_path)
    yield db
    # Cleanup
    if Path(db_path).exists():
        Path(db_path).unlink()


@pytest.fixture
def context_manager(temp_db):
    """Create a context manager for testing."""
    return ConversationContextManager(temp_db, default_limit=10)


@pytest.mark.asyncio
async def test_get_context(context_manager, temp_db):
    """Test getting conversation context."""
    await temp_db.initialize()

    # Save some messages
    await context_manager.save_message(
        chat_id=123,
        user_id=456,
        message="Hello",
        role="user",
    )
    await context_manager.save_message(
        chat_id=123,
        user_id=456,
        message="Hi there!",
        role="assistant",
    )

    context = await context_manager.get_context(chat_id=123, user_id=456)
    assert context.chat_id == 123
    assert context.user_id == 456
    assert len(context.messages) == 2


@pytest.mark.asyncio
async def test_save_message(context_manager, temp_db):
    """Test saving a message through context manager."""
    await temp_db.initialize()

    await context_manager.save_message(
        chat_id=123,
        user_id=456,
        message="Test message",
        role="user",
        message_id=789,
    )

    messages = await context_manager.get_recent_messages(chat_id=123)
    assert len(messages) == 1
    assert messages[0].message_text == "Test message"


@pytest.mark.asyncio
async def test_format_for_llm(context_manager, temp_db):
    """Test formatting context for LLM."""
    await temp_db.initialize()

    await context_manager.save_message(
        chat_id=123,
        user_id=456,
        message="Hello",
        role="user",
    )
    await context_manager.save_message(
        chat_id=123,
        user_id=456,
        message="Hi!",
        role="assistant",
    )

    context = await context_manager.get_context(chat_id=123, user_id=456)
    formatted = context.format_for_llm()

    assert "User: Hello" in formatted
    assert "Assistant: Hi!" in formatted

