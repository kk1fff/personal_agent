"""Tests for Context Manager tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.tools.context_manager import ContextManagerTool
from src.context.models import ConversationContext, Message


@pytest.fixture
def mock_context_manager():
    """Create a mock context manager."""
    manager = MagicMock()
    manager.get_recent_messages = AsyncMock()
    return manager


@pytest.fixture
def conversation_context():
    """Create a conversation context for testing."""
    return ConversationContext(
        chat_id=123,
        user_id=456,
        messages=[],  # Empty - context manager tool will retrieve from DB
        recent_limit=5,
    )


@pytest.fixture
def sample_messages():
    """Create sample messages for testing."""
    return [
        Message(
            chat_id=123,
            user_id=456,
            message_text="Hello",
            role="user",
            timestamp=datetime.now(),
        ),
        Message(
            chat_id=123,
            user_id=456,
            message_text="Hi there!",
            role="assistant",
            timestamp=datetime.now(),
        ),
        Message(
            chat_id=123,
            user_id=456,
            message_text="How are you?",
            role="user",
            timestamp=datetime.now(),
        ),
    ]


@pytest.mark.asyncio
async def test_context_manager_retrieves_messages(
    mock_context_manager, conversation_context, sample_messages
):
    """Test that context manager tool retrieves messages."""
    # Setup mock
    mock_context_manager.get_recent_messages.return_value = sample_messages

    # Create tool
    tool = ContextManagerTool(mock_context_manager, max_history=5)

    # Execute
    result = await tool.execute(conversation_context, count=3)

    # Verify
    assert result.success is True
    assert result.data["count"] == 3
    assert len(result.data["messages"]) == 3
    assert "User: Hello" in result.message
    assert "Assistant: Hi there!" in result.message
    assert "User: How are you?" in result.message

    # Verify context manager was called correctly
    mock_context_manager.get_recent_messages.assert_called_once_with(
        chat_id=123, limit=3
    )


@pytest.mark.asyncio
async def test_context_manager_respects_max_history(
    mock_context_manager, conversation_context, sample_messages
):
    """Test that tool enforces max_history limit."""
    # Setup mock
    mock_context_manager.get_recent_messages.return_value = sample_messages

    # Create tool with max_history=2
    tool = ContextManagerTool(mock_context_manager, max_history=2)

    # Request more than max_history
    result = await tool.execute(conversation_context, count=10)

    # Verify that count was capped at max_history
    assert result.success is True
    mock_context_manager.get_recent_messages.assert_called_once_with(
        chat_id=123, limit=2  # Should be capped at max_history
    )


@pytest.mark.asyncio
async def test_context_manager_validates_count(
    mock_context_manager, conversation_context
):
    """Test that tool validates count parameter."""
    tool = ContextManagerTool(mock_context_manager, max_history=5)

    # Test negative count
    result = await tool.execute(conversation_context, count=-1)
    assert result.success is False
    assert "positive integer" in result.error

    # Test zero count
    result = await tool.execute(conversation_context, count=0)
    assert result.success is False
    assert "positive integer" in result.error

    # Test non-integer count
    result = await tool.execute(conversation_context, count="five")
    assert result.success is False
    assert "positive integer" in result.error


@pytest.mark.asyncio
async def test_context_manager_default_count(
    mock_context_manager, conversation_context, sample_messages
):
    """Test that tool uses max_history as default count."""
    # Setup mock
    mock_context_manager.get_recent_messages.return_value = sample_messages

    # Create tool
    tool = ContextManagerTool(mock_context_manager, max_history=5)

    # Execute without count parameter
    result = await tool.execute(conversation_context)

    # Verify default count is max_history
    assert result.success is True
    mock_context_manager.get_recent_messages.assert_called_once_with(
        chat_id=123, limit=5
    )


@pytest.mark.asyncio
async def test_context_manager_empty_history(
    mock_context_manager, conversation_context
):
    """Test that tool handles empty history gracefully."""
    # Setup mock to return empty list
    mock_context_manager.get_recent_messages.return_value = []

    # Create tool
    tool = ContextManagerTool(mock_context_manager, max_history=5)

    # Execute
    result = await tool.execute(conversation_context, count=5)

    # Verify
    assert result.success is True
    assert result.data["count"] == 0
    assert len(result.data["messages"]) == 0
    assert "Retrieved 0 previous message(s)" in result.message


@pytest.mark.asyncio
async def test_context_manager_handles_exceptions(
    mock_context_manager, conversation_context
):
    """Test that tool handles database exceptions gracefully."""
    # Setup mock to raise exception
    mock_context_manager.get_recent_messages.side_effect = Exception(
        "Database error"
    )

    # Create tool
    tool = ContextManagerTool(mock_context_manager, max_history=5)

    # Execute
    result = await tool.execute(conversation_context, count=3)

    # Verify error is handled
    assert result.success is False
    assert "Failed to retrieve conversation history" in result.error
    assert "Database error" in result.error


def test_context_manager_tool_name():
    """Test getting tool name."""
    mock_manager = MagicMock()
    tool = ContextManagerTool(mock_manager, max_history=5)
    assert tool.get_name() == "get_conversation_history"


def test_context_manager_tool_description():
    """Test getting tool description."""
    mock_manager = MagicMock()
    tool = ContextManagerTool(mock_manager, max_history=5)
    description = tool.get_description()
    assert "retrieve previous messages" in description.lower()
    assert "5 previous messages" in description


def test_context_manager_tool_schema():
    """Test getting tool schema."""
    mock_manager = MagicMock()
    tool = ContextManagerTool(mock_manager, max_history=5)
    schema = tool.get_schema()

    assert schema["name"] == "get_conversation_history"
    assert "parameters" in schema
    assert "count" in schema["parameters"]["properties"]
    assert schema["parameters"]["properties"]["count"]["type"] == "integer"
    assert schema["parameters"]["properties"]["count"]["minimum"] == 1
    assert schema["parameters"]["properties"]["count"]["maximum"] == 5
