"""Tests for tool registry."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.tools.registry import ToolRegistry
from src.tools.chat_reply import ChatReplyTool
from src.config.config_schema import AppConfig, TelegramConfig, LLMConfig, OllamaConfig, ToolsConfig


@pytest.fixture
def basic_config():
    """Create a basic configuration."""
    return AppConfig(
        telegram=TelegramConfig(bot_token="test_token", mode="poll"),
        llm=LLMConfig(
            provider="ollama",
            ollama=OllamaConfig(model="llama2"),
        ),
        tools=ToolsConfig(),
    )


def test_register_tool():
    """Test registering a tool."""
    registry = ToolRegistry()
    tool = ChatReplyTool(AsyncMock())

    registry.register_tool(tool)

    assert registry.get_tool("chat_reply") == tool
    assert len(registry.get_all_tools()) == 1


def test_get_tool_not_found():
    """Test getting a non-existent tool."""
    registry = ToolRegistry()
    assert registry.get_tool("nonexistent") is None


def test_get_all_tools():
    """Test getting all tools."""
    registry = ToolRegistry()
    tool1 = ChatReplyTool(AsyncMock())
    tool2 = ChatReplyTool(AsyncMock())

    registry.register_tool(tool1)
    
    # Mock tool2 name to avoid collision
    tool2.get_name = MagicMock(return_value="chat_reply_2")
    registry.register_tool(tool2)

    tools = registry.get_all_tools()
    assert len(tools) == 2
    assert tool1 in tools
    assert tool2 in tools


def test_initialize_tools(basic_config):
    """Test initializing tools from configuration."""
    registry = ToolRegistry()
    send_message_callback = AsyncMock()

    registry.initialize_tools(basic_config, send_message_callback)

    # Should always have chat_reply
    assert registry.get_tool("chat_reply") is not None
    tools = registry.get_all_tools()
    assert len(tools) >= 1


def test_initialize_tools_with_context_manager(basic_config):
    """Test initializing tools with context manager."""
    registry = ToolRegistry()
    send_message_callback = AsyncMock()
    context_manager = MagicMock()

    registry.initialize_tools(basic_config, send_message_callback, context_manager)

    # Should have chat_reply and get_conversation_history
    assert registry.get_tool("chat_reply") is not None
    assert registry.get_tool("get_conversation_history") is not None

