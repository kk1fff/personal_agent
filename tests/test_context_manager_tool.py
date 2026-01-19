"""Tests for Context Manager tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.tools.context_manager import ContextManagerTool
from src.context.models import ConversationContext


@pytest.fixture
def mock_context_manager():
    """Create a mock context manager."""
    manager = MagicMock()
    manager.get_llm_context = AsyncMock()
    return manager


@pytest.fixture
def conversation_context():
    """Create a conversation context for testing."""
    return ConversationContext(
        chat_id=123,
        user_id=456,
        messages=[],
    )


@pytest.mark.asyncio
async def test_context_manager_tool_execute(
    mock_context_manager, conversation_context
):
    """Test that tool executes llm context retrieval."""
    # Setup mock
    mock_context_manager.get_llm_context.return_value = ("Summarized context", 5)

    # Create tool
    tool = ContextManagerTool(mock_context_manager)

    # Execute
    result = await tool.execute(conversation_context, query="What did we discuss?")

    # Verify
    assert result.success is True
    assert result.data["count"] == 5
    assert result.data["summary"] == "Summarized context"
    assert "Summarized context" in result.message

    # Verify context manager was called correctly
    mock_context_manager.get_llm_context.assert_called_once_with(
        chat_id=123,
        user_id=456,
        query="What did we discuss?",
    )


@pytest.mark.asyncio
async def test_context_manager_tool_requires_query(
    mock_context_manager, conversation_context
):
    """Test that tool fails if query is missing."""
    tool = ContextManagerTool(mock_context_manager)

    # Execute without query
    result = await tool.execute(conversation_context)

    # Verify
    assert result.success is False
    assert "Query parameter is required" in result.error


@pytest.mark.asyncio
async def test_context_manager_tool_handles_exceptions(
    mock_context_manager, conversation_context
):
    """Test that tool handles backend exceptions."""
    # Setup mock to raise exception
    mock_context_manager.get_llm_context.side_effect = Exception("LLM error")

    tool = ContextManagerTool(mock_context_manager)

    # Execute
    result = await tool.execute(conversation_context, query="test")

    # Verify
    assert result.success is False
    assert "Failed to generate LLM context" in result.error
    assert "LLM error" in result.error


def test_context_manager_tool_schema():
    """Test tool schema."""
    mock_manager = MagicMock()
    tool = ContextManagerTool(mock_manager)
    schema = tool.get_schema()

    assert schema["name"] == "get_conversation_history"
    assert "query" in schema["parameters"]["properties"]
    assert "query" in schema["parameters"]["required"]
    assert "mode" not in schema["parameters"]["properties"]
