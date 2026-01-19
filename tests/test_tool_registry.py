"""Tests for tool registry."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.tools.registry import ToolRegistry
from src.tools.base import BaseTool
from src.config.config_schema import AppConfig, TelegramConfig, LLMConfig, OllamaConfig, ToolsConfig


class MockTool(BaseTool):
    """Mock tool for testing."""

    def __init__(self, name: str = "mock_tool"):
        super().__init__(name=name, description="A mock tool for testing")

    async def execute(self, context, **kwargs):
        return {"success": True}

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "object", "properties": {}},
        }


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
    tool = MockTool("test_tool")

    registry.register_tool(tool)

    assert registry.get_tool("test_tool") == tool
    assert len(registry.get_all_tools()) == 1


def test_get_tool_not_found():
    """Test getting a non-existent tool."""
    registry = ToolRegistry()
    assert registry.get_tool("nonexistent") is None


def test_get_all_tools():
    """Test getting all tools."""
    registry = ToolRegistry()
    tool1 = MockTool("tool_1")
    tool2 = MockTool("tool_2")

    registry.register_tool(tool1)
    registry.register_tool(tool2)

    tools = registry.get_all_tools()
    assert len(tools) == 2
    assert tool1 in tools
    assert tool2 in tools


def test_initialize_tools(basic_config):
    """Test initializing tools from configuration."""
    registry = ToolRegistry()

    registry.initialize_tools(basic_config)

    # With basic config and no context_manager, no tools should be registered
    tools = registry.get_all_tools()
    assert len(tools) == 0


def test_initialize_tools_with_context_manager(basic_config):
    """Test initializing tools with context manager."""
    registry = ToolRegistry()
    context_manager = MagicMock()

    registry.initialize_tools(basic_config, context_manager)

    # Should have get_conversation_history tool
    assert registry.get_tool("get_conversation_history") is not None
    tools = registry.get_all_tools()
    assert len(tools) == 1
