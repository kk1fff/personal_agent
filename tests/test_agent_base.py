"""Tests for agent base classes."""

import pytest
from unittest.mock import MagicMock

from src.agent.base import AgentContext, AgentResult, BaseAgent


def test_agent_context_creation():
    """Test creating an agent context."""
    context = AgentContext(
        chat_id=123,
        user_id=456,
        session_id="session_123",
    )

    assert context.chat_id == 123
    assert context.user_id == 456
    assert context.session_id == "session_123"
    assert context.message_history == []
    assert context.metadata == {}
    assert context.parent_trace_id is None
    assert context.trace_id is not None


def test_agent_context_with_history():
    """Test agent context with message history."""
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]

    context = AgentContext(
        chat_id=123,
        user_id=456,
        session_id="session_123",
        message_history=history,
    )

    assert len(context.message_history) == 2
    assert context.message_history[0]["role"] == "user"


def test_agent_context_with_metadata():
    """Test agent context with metadata."""
    metadata = {"timezone": "UTC", "language": "en"}

    context = AgentContext(
        chat_id=123,
        user_id=456,
        session_id="session_123",
        metadata=metadata,
    )

    assert context.metadata["timezone"] == "UTC"
    assert context.metadata["language"] == "en"


def test_agent_context_child_trace():
    """Test creating child context with new trace."""
    context = AgentContext(
        chat_id=123,
        user_id=456,
        session_id="session_123",
        message_history=[{"role": "user", "content": "test"}],
        metadata={"key": "value"},
    )

    original_trace_id = context.trace_id
    child = context.with_child_trace()

    # Child should have new trace ID
    assert child.trace_id != original_trace_id
    # Parent trace should be set
    assert child.parent_trace_id == original_trace_id
    # Other fields should be copied
    assert child.chat_id == context.chat_id
    assert child.user_id == context.user_id
    assert child.session_id == context.session_id
    assert len(child.message_history) == len(context.message_history)
    assert child.metadata["key"] == "value"


def test_agent_result_creation():
    """Test creating an agent result."""
    result = AgentResult(
        success=True,
        response_text="Hello!",
        agent_name="test_agent",
        trace_id="trace123",
    )

    assert result.success is True
    assert result.response_text == "Hello!"
    assert result.agent_name == "test_agent"
    assert result.trace_id == "trace123"
    assert result.structured_data is None
    assert result.tool_calls_made == []
    assert result.processing_time_ms == 0


def test_agent_result_with_structured_data():
    """Test agent result with structured data."""
    result = AgentResult(
        success=True,
        response_text="Found results",
        structured_data={"count": 5, "items": ["a", "b"]},
        agent_name="notion_specialist",
        trace_id="trace123",
        tool_calls_made=["notion_search"],
        processing_time_ms=150.5,
    )

    assert result.structured_data["count"] == 5
    assert len(result.tool_calls_made) == 1
    assert result.processing_time_ms == 150.5


def test_agent_result_failure():
    """Test agent result for failure case."""
    result = AgentResult(
        success=False,
        response_text="Error occurred",
        agent_name="test_agent",
        trace_id="trace123",
    )

    assert result.success is False
    assert "Error" in result.response_text


class MockAgent(BaseAgent):
    """Mock agent for testing."""

    async def process(self, message, context):
        return AgentResult(
            success=True,
            response_text="Mock response",
            agent_name=self.name,
            trace_id=context.trace_id,
        )

    def get_system_prompt(self, context):
        return f"System prompt with timezone: {context.metadata.get('timezone', 'UTC')}"


def test_base_agent_properties():
    """Test base agent properties."""
    agent = MockAgent(
        name="test_agent",
        description="A test agent",
        llm=MagicMock(),
        system_prompt="Test prompt",
        tools=[],
    )

    assert agent.get_name() == "test_agent"
    assert agent.get_description() == "A test agent"
    assert agent.get_tools() == []


def test_base_agent_with_tools():
    """Test base agent with tools."""
    mock_tool = MagicMock()
    mock_tool.get_name.return_value = "mock_tool"

    agent = MockAgent(
        name="test_agent",
        description="A test agent",
        llm=MagicMock(),
        system_prompt="Test prompt",
        tools=[mock_tool],
    )

    tools = agent.get_tools()
    assert len(tools) == 1
    assert tools[0].get_name() == "mock_tool"


@pytest.mark.asyncio
async def test_mock_agent_process():
    """Test agent process method."""
    agent = MockAgent(
        name="test_agent",
        description="A test agent",
        llm=MagicMock(),
        system_prompt="Test prompt",
    )

    context = AgentContext(
        chat_id=123,
        user_id=456,
        session_id="session",
    )

    result = await agent.process("Hello", context)

    assert result.success is True
    assert result.response_text == "Mock response"
    assert result.agent_name == "test_agent"


def test_agent_system_prompt():
    """Test agent system prompt generation."""
    agent = MockAgent(
        name="test_agent",
        description="A test agent",
        llm=MagicMock(),
        system_prompt="Test prompt",
    )

    context = AgentContext(
        chat_id=123,
        user_id=456,
        session_id="session",
        metadata={"timezone": "America/New_York"},
    )

    prompt = agent.get_system_prompt(context)

    assert "America/New_York" in prompt
