"""Tests for smart context retrieval (time-gap clustering)."""

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.context.conversation_db import ConversationDB
from src.context.context_manager import ConversationContextManager


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    db_path = "test_smart_context.db"
    db = ConversationDB(db_path)
    yield db
    # Cleanup
    if Path(db_path).exists():
        Path(db_path).unlink()


@pytest.fixture
def context_manager(temp_db):
    """Create a context manager with test settings."""
    return ConversationContextManager(
        temp_db,
        default_limit=10,
        time_gap_threshold_minutes=60,
        lookback_limit=25,
    )


@pytest.mark.asyncio
async def test_get_smart_context_empty(context_manager, temp_db):
    """Test smart context when no messages exist."""
    await temp_db.initialize()

    context, count = await context_manager.get_smart_context(
        chat_id=123,
        user_id=456,
    )

    assert count == 0
    assert len(context.messages) == 0


@pytest.mark.asyncio
async def test_get_smart_context_single_session(context_manager, temp_db):
    """Test that messages within threshold are grouped together."""
    await temp_db.initialize()

    # Create 5 messages all within the threshold (simulating a single session)
    # They will all have timestamps very close together since we're calling
    # save_message in quick succession
    for i in range(5):
        await temp_db.save_message(
            chat_id=123,
            user_id=456,
            message_text=f"Message {i}",
            role="user",
        )

    # Get smart context - all should be in same session
    context, count = await context_manager.get_smart_context(
        chat_id=123,
        user_id=456,
    )

    # All 5 messages should be in the same session
    assert count == 5
    assert len(context.messages) == 5


@pytest.mark.asyncio
async def test_get_message_by_id(temp_db):
    """Test fetching specific message by Telegram message ID."""
    await temp_db.initialize()

    await temp_db.save_message(
        chat_id=123,
        user_id=456,
        message_text="Target message",
        role="user",
        message_id=999,
    )

    await temp_db.save_message(
        chat_id=123,
        user_id=456,
        message_text="Another message",
        role="user",
        message_id=1000,
    )

    # Fetch existing message
    msg = await temp_db.get_message_by_id(123, 999)
    assert msg is not None
    assert msg.message_text == "Target message"
    assert msg.message_id == 999

    # Fetch non-existent message
    msg = await temp_db.get_message_by_id(123, 888)
    assert msg is None

    # Fetch from wrong chat
    msg = await temp_db.get_message_by_id(456, 999)
    assert msg is None


@pytest.mark.asyncio
async def test_reply_to_message_storage(temp_db):
    """Test that reply_to_message_id is stored and retrieved."""
    await temp_db.initialize()

    # Save original message
    await temp_db.save_message(
        chat_id=123,
        user_id=456,
        message_text="Original message",
        role="user",
        message_id=100,
    )

    # Save reply message
    await temp_db.save_message(
        chat_id=123,
        user_id=456,
        message_text="Reply message",
        role="user",
        message_id=101,
        reply_to_message_id=100,
    )

    # Fetch reply and verify reply_to_message_id
    msg = await temp_db.get_message_by_id(123, 101)
    assert msg is not None
    assert msg.reply_to_message_id == 100


@pytest.mark.asyncio
async def test_get_messages_for_clustering(temp_db):
    """Test that clustering retrieval returns messages in DESC order."""
    await temp_db.initialize()

    for i in range(5):
        await temp_db.save_message(
            chat_id=123,
            user_id=456,
            message_text=f"Message {i}",
            role="user",
        )

    messages = await temp_db.get_messages_for_clustering(123, limit=10)

    # Should be in reverse chronological order (newest first)
    assert len(messages) == 5
    # The last message saved should be first
    assert messages[0].message_text == "Message 4"
    assert messages[4].message_text == "Message 0"


@pytest.mark.asyncio
async def test_context_manager_get_message_by_id(context_manager, temp_db):
    """Test context manager wrapper for get_message_by_id."""
    await temp_db.initialize()

    await temp_db.save_message(
        chat_id=123,
        user_id=456,
        message_text="Test message",
        role="user",
        message_id=555,
    )

    msg = await context_manager.get_message_by_id(123, 555)
    assert msg is not None
    assert msg.message_text == "Test message"


@pytest.mark.asyncio
async def test_context_manager_save_with_reply_to(context_manager, temp_db):
    """Test context manager saves reply_to_message_id."""
    await temp_db.initialize()

    await context_manager.save_message(
        chat_id=123,
        user_id=456,
        message="Test reply",
        role="user",
        message_id=200,
        reply_to_message_id=100,
    )

    messages = await temp_db.get_recent_messages(123, limit=10)
    assert len(messages) == 1
    assert messages[0].reply_to_message_id == 100
