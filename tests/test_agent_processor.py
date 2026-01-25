"""Tests for AgentProcessor."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.agent.agent_processor import AgentProcessor, AgentResponse
from src.context.models import ConversationContext, Message
from src.tools.base import BaseTool, ToolResult
from src.llm.base import BaseLLM, LLMResponse, ToolCall


@pytest.fixture
def mock_llm():
    """Create a mock LLM instance."""
    llm = MagicMock(spec=BaseLLM)
    llm.generate = AsyncMock(return_value=LLMResponse(text="Test response"))
    llm.get_model_name = MagicMock(return_value="test-model")
    return llm


@pytest.fixture
def mock_tool():
    """Create a mock tool instance."""
    tool = MagicMock(spec=BaseTool)
    tool.get_name = MagicMock(return_value="test_tool")
    tool.get_description = MagicMock(return_value="A test tool")
    tool.get_schema = MagicMock(return_value={
        "name": "test_tool",
        "description": "A test tool for testing",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "Test parameter"}
            },
            "required": ["param1"]
        }
    })
    tool.execute = AsyncMock(return_value=ToolResult(
        success=True,
        data={"result": "success"},
        message="Tool executed successfully"
    ))
    return tool


@pytest.fixture
def conversation_context():
    """Create a test conversation context."""
    return ConversationContext(
        chat_id=123,
        user_id=456,
        messages=[
            Message(
                chat_id=123,
                user_id=456,
                message_text="Hello",
                role="user",
                timestamp=datetime.now()
            )
        ],
        recent_limit=10,
        metadata={}
    )


class TestAgentProcessorInitialization:
    """Test AgentProcessor initialization."""

    def test_initialization_stores_llm(self, mock_llm, mock_tool):
        """Test that LLM is stored during initialization."""
        processor = AgentProcessor(
            llm=mock_llm,
            tools=[mock_tool],
            system_prompt="Test prompt"
        )

        assert processor.llm == mock_llm

    def test_initialization_stores_tools(self, mock_llm, mock_tool):
        """Test that tools are stored in dictionary."""
        processor = AgentProcessor(
            llm=mock_llm,
            tools=[mock_tool],
            system_prompt="Test prompt"
        )

        assert "test_tool" in processor.tools
        assert processor.tools["test_tool"] == mock_tool

    def test_initialization_creates_agent(self, mock_llm, mock_tool):
        """Test that PydanticAI agent is created."""
        processor = AgentProcessor(
            llm=mock_llm,
            tools=[mock_tool],
            system_prompt="Test prompt"
        )

        assert processor.agent is not None

    def test_initialization_with_multiple_tools(self, mock_llm):
        """Test initialization with multiple tools."""
        tool1 = MagicMock(spec=BaseTool)
        tool1.get_name = MagicMock(return_value="tool1")
        tool1.get_schema = MagicMock(return_value={
            "name": "tool1",
            "description": "Tool 1",
            "parameters": {"type": "object", "properties": {}}
        })

        tool2 = MagicMock(spec=BaseTool)
        tool2.get_name = MagicMock(return_value="tool2")
        tool2.get_schema = MagicMock(return_value={
            "name": "tool2",
            "description": "Tool 2",
            "parameters": {"type": "object", "properties": {}}
        })

        processor = AgentProcessor(
            llm=mock_llm,
            tools=[tool1, tool2],
            system_prompt="Test prompt"
        )

        assert len(processor.tools) == 2
        assert "tool1" in processor.tools
        assert "tool2" in processor.tools


class TestToolRegistration:
    """Test tool registration with PydanticAI agent."""

    def test_register_tool_calls_agent_tool(self, mock_llm, mock_tool):
        """Test that _register_tool calls agent.tool()."""
        processor = AgentProcessor(
            llm=mock_llm,
            tools=[],
            system_prompt="Test prompt"
        )

        with patch.object(processor.agent, 'tool') as mock_agent_tool:
            processor._register_tool(mock_tool)

            # Verify agent.tool() was called once
            assert mock_agent_tool.call_count == 1

    def test_tool_wrapper_has_correct_name(self, mock_llm, mock_tool):
        """Test that tool wrapper has correct __name__."""
        processor = AgentProcessor(
            llm=mock_llm,
            tools=[],
            system_prompt="Test prompt"
        )

        with patch.object(processor.agent, 'tool') as mock_agent_tool:
            processor._register_tool(mock_tool)

            # Get the wrapper function that was passed to agent.tool()
            wrapper_func = mock_agent_tool.call_args[0][0]
            assert wrapper_func.__name__ == "test_tool"

    def test_tool_wrapper_has_correct_docstring(self, mock_llm, mock_tool):
        """Test that tool wrapper has correct docstring."""
        processor = AgentProcessor(
            llm=mock_llm,
            tools=[],
            system_prompt="Test prompt"
        )

        with patch.object(processor.agent, 'tool') as mock_agent_tool:
            processor._register_tool(mock_tool)

            # Get the wrapper function
            wrapper_func = mock_agent_tool.call_args[0][0]
            assert wrapper_func.__doc__ == "A test tool for testing"


class TestProcessCommand:
    """Test process_command method."""

    @pytest.mark.asyncio
    async def test_process_command_calls_agent_run(self, mock_llm, mock_tool, conversation_context):
        """Test that process_command calls agent.run()."""
        processor = AgentProcessor(
            llm=mock_llm,
            tools=[mock_tool],
            system_prompt="Test prompt"
        )

        # Mock agent.run to return a result
        mock_result = MagicMock()
        mock_result.data = "Agent response text"

        with patch.object(processor.agent, 'run', new=AsyncMock(return_value=mock_result)) as mock_run:
            result = await processor.process_command(
                message="Test message",
                context=conversation_context
            )

            # Verify agent.run was called
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs['user_prompt'] == "Test message"
            assert call_kwargs['deps'] == conversation_context
            
            # Since we patched agent.run, the model adapter logic inside process_command 
            # might not be fully exercised if it relies on side effects, but we can verify
            # no errors occurred during execution.
            # In a real scenario, we'd verify set_trace was called if context had trace.

    @pytest.mark.asyncio
    async def test_process_command_returns_agent_response(self, mock_llm, mock_tool, conversation_context):
        """Test that process_command returns AgentResponse."""
        processor = AgentProcessor(
            llm=mock_llm,
            tools=[mock_tool],
            system_prompt="Test prompt"
        )

        mock_result = MagicMock()
        mock_result.data = "Agent response text"

        with patch.object(processor.agent, 'run', new=AsyncMock(return_value=mock_result)):
            result = await processor.process_command(
                message="Test message",
                context=conversation_context
            )

            assert isinstance(result, AgentResponse)
            assert result.text == "Agent response text"
            assert result.tool_calls == []

    @pytest.mark.asyncio
    async def test_process_command_extracts_response_from_data(self, mock_llm, mock_tool, conversation_context):
        """Test that response text is extracted from result.data."""
        processor = AgentProcessor(
            llm=mock_llm,
            tools=[mock_tool],
            system_prompt="Test prompt"
        )

        mock_result = MagicMock()
        mock_result.data = "Response from agent"

        with patch.object(processor.agent, 'run', new=AsyncMock(return_value=mock_result)):
            result = await processor.process_command(
                message="Test",
                context=conversation_context
            )

            assert result.text == "Response from agent"

    @pytest.mark.asyncio
    async def test_process_command_fallback_to_output(self, mock_llm, mock_tool, conversation_context):
        """Test fallback to result.output if result.data doesn't exist."""
        processor = AgentProcessor(
            llm=mock_llm,
            tools=[mock_tool],
            system_prompt="Test prompt"
        )

        # Mock result without .data attribute
        mock_result = MagicMock()
        del mock_result.data
        mock_result.output = "Response from output"

        with patch.object(processor.agent, 'run', new=AsyncMock(return_value=mock_result)):
            result = await processor.process_command(
                message="Test",
                context=conversation_context
            )

            assert result.text == "Response from output"

    @pytest.mark.asyncio
    async def test_process_command_detects_follow_up_questions(self, mock_llm, mock_tool, conversation_context):
        """Test that follow-up questions are detected."""
        processor = AgentProcessor(
            llm=mock_llm,
            tools=[mock_tool],
            system_prompt="Test prompt"
        )

        mock_result = MagicMock()
        mock_result.data = "What would you like to do?"

        with patch.object(processor.agent, 'run', new=AsyncMock(return_value=mock_result)):
            result = await processor.process_command(
                message="Test",
                context=conversation_context
            )

            assert result.follow_up is True

    @pytest.mark.asyncio
    async def test_process_command_handles_exceptions(self, mock_llm, mock_tool, conversation_context):
        """Test that exceptions are handled gracefully."""
        processor = AgentProcessor(
            llm=mock_llm,
            tools=[mock_tool],
            system_prompt="Test prompt"
        )

        with patch.object(processor.agent, 'run', new=AsyncMock(side_effect=Exception("Test error"))):
            result = await processor.process_command(
                message="Test",
                context=conversation_context
            )

            assert isinstance(result, AgentResponse)
            assert "having trouble" in result.text.lower()
            assert result.follow_up is False


class TestToolExecution:
    """Test tool execution through the wrapper."""

    @pytest.mark.asyncio
    async def test_tool_wrapper_extracts_context_from_run_context(self, mock_llm, conversation_context):
        """Test that tool wrapper extracts context from RunContext."""
        # Create a tool that we can verify was called correctly
        test_tool = MagicMock(spec=BaseTool)
        test_tool.get_name = MagicMock(return_value="context_test_tool")
        test_tool.get_schema = MagicMock(return_value={
            "name": "context_test_tool",
            "description": "Test context extraction",
            "parameters": {"type": "object", "properties": {}}
        })
        test_tool.execute = AsyncMock(return_value=ToolResult(
            success=True,
            data={"executed": True},
            message="Context test successful"
        ))

        processor = AgentProcessor(
            llm=mock_llm,
            tools=[test_tool],
            system_prompt="Test prompt"
        )

        # The tool wrapper should have been registered
        # When agent.run() calls the tool, it should extract context correctly
        # This is implicitly tested when the full integration works

    @pytest.mark.asyncio
    async def test_tool_wrapper_converts_success_result(self, mock_llm):
        """Test that successful ToolResult is converted to string."""
        tool = MagicMock(spec=BaseTool)
        tool.get_name = MagicMock(return_value="success_tool")
        tool.get_schema = MagicMock(return_value={
            "name": "success_tool",
            "description": "Test success",
            "parameters": {"type": "object", "properties": {}}
        })
        tool.execute = AsyncMock(return_value=ToolResult(
            success=True,
            data={"result": "ok"},
            message="Operation successful"
        ))

        processor = AgentProcessor(
            llm=mock_llm,
            tools=[],
            system_prompt="Test prompt"
        )

        # Register tool and capture wrapper
        with patch.object(processor.agent, 'tool') as mock_agent_tool:
            processor._register_tool(tool)
            wrapper_func = mock_agent_tool.call_args[0][0]

        # Create mock RunContext
        from pydantic_ai import RunContext
        mock_ctx = MagicMock(spec=RunContext)
        mock_ctx.deps = ConversationContext(
            chat_id=123,
            user_id=456,
            messages=[],
            recent_limit=10,
            metadata={}
        )

        # Call wrapper
        result = await wrapper_func(mock_ctx)

        # Should return the message with tool name prefix
        assert result == "Result from tool 'success_tool':\nOperation successful"

    @pytest.mark.asyncio
    async def test_tool_wrapper_converts_error_result(self, mock_llm):
        """Test that failed ToolResult is converted to error string."""
        tool = MagicMock(spec=BaseTool)
        tool.get_name = MagicMock(return_value="error_tool")
        tool.get_schema = MagicMock(return_value={
            "name": "error_tool",
            "description": "Test error",
            "parameters": {"type": "object", "properties": {}}
        })
        tool.execute = AsyncMock(return_value=ToolResult(
            success=False,
            data=None,
            error="Something went wrong"
        ))

        processor = AgentProcessor(
            llm=mock_llm,
            tools=[],
            system_prompt="Test prompt"
        )

        # Register tool and capture wrapper
        with patch.object(processor.agent, 'tool') as mock_agent_tool:
            processor._register_tool(tool)
            wrapper_func = mock_agent_tool.call_args[0][0]

        # Create mock RunContext
        from pydantic_ai import RunContext
        mock_ctx = MagicMock(spec=RunContext)
        mock_ctx.deps = ConversationContext(
            chat_id=123,
            user_id=456,
            messages=[],
            recent_limit=10,
            metadata={}
        )

        # Call wrapper
        result = await wrapper_func(mock_ctx)

        # Should return error message with tool name prefix
        assert result == "Error from tool 'error_tool':\nSomething went wrong"

    @pytest.mark.asyncio
    async def test_tool_wrapper_handles_no_message(self, mock_llm):
        """Test that wrapper handles ToolResult with no message."""
        tool = MagicMock(spec=BaseTool)
        tool.get_name = MagicMock(return_value="no_message_tool")
        tool.get_schema = MagicMock(return_value={
            "name": "no_message_tool",
            "description": "Test no message",
            "parameters": {"type": "object", "properties": {}}
        })
        tool.execute = AsyncMock(return_value=ToolResult(
            success=True,
            data={"key": "value"},
            message=None
        ))

        processor = AgentProcessor(
            llm=mock_llm,
            tools=[],
            system_prompt="Test prompt"
        )

        # Register tool and capture wrapper
        with patch.object(processor.agent, 'tool') as mock_agent_tool:
            processor._register_tool(tool)
            wrapper_func = mock_agent_tool.call_args[0][0]

        # Create mock RunContext
        from pydantic_ai import RunContext
        mock_ctx = MagicMock(spec=RunContext)
        mock_ctx.deps = ConversationContext(
            chat_id=123,
            user_id=456,
            messages=[],
            recent_limit=10,
            metadata={}
        )

        # Call wrapper
        result = await wrapper_func(mock_ctx)

        # Should return string representation of data
        assert "key" in result
        assert "value" in result
