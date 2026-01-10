"""Tests for base tool class."""

import pytest
from unittest.mock import AsyncMock

from src.tools.base import BaseTool, ToolResult
from src.context.models import ConversationContext, Message
from datetime import datetime


class TestTool(BaseTool):
    """Test tool implementation."""

    def __init__(self):
        super().__init__(name="test_tool", description="A test tool")

    async def execute(self, context: ConversationContext, **kwargs) -> ToolResult:
        """Execute the test tool."""
        return ToolResult(
            success=True,
            data={"test": "data"},
            message="Test executed successfully",
        )

    def get_schema(self):
        """Get tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {},
            },
        }


@pytest.fixture
def conversation_context():
    """Create a conversation context for testing."""
    return ConversationContext(
        chat_id=123,
        user_id=456,
        messages=[
            Message(
                chat_id=123,
                user_id=456,
                message_text="Hello",
                role="user",
                timestamp=datetime.now(),
            )
        ],
    )


@pytest.mark.asyncio
async def test_tool_execute(conversation_context):
    """Test tool execution."""
    tool = TestTool()
    result = await tool.execute(conversation_context)

    assert result.success is True
    assert result.data == {"test": "data"}
    assert result.message == "Test executed successfully"


def test_tool_get_name():
    """Test getting tool name."""
    tool = TestTool()
    assert tool.get_name() == "test_tool"


def test_tool_get_description():
    """Test getting tool description."""
    tool = TestTool()
    assert tool.get_description() == "A test tool"


def test_tool_get_schema():
    """Test getting tool schema."""
    tool = TestTool()
    schema = tool.get_schema()

    assert schema["name"] == "test_tool"
    assert schema["description"] == "A test tool"
    assert "parameters" in schema


def test_tool_validate_input():
    """Test input validation."""
    tool = TestTool()
    # Default implementation should return True
    assert tool.validate_input() is True

