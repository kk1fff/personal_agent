"""Tests for Gemini LLM implementation."""

import pytest
from src.llm.gemini_llm import GeminiLLM
from src.llm.base import ToolCall


class TestParseToolCallFromText:
    """Tests for _parse_tool_call_from_text method."""

    @pytest.fixture
    def gemini_llm(self):
        """Create a GeminiLLM instance for testing."""
        # Use a placeholder API key since we're not making actual API calls
        return GeminiLLM(api_key="test_key")

    def test_parse_valid_tool_call_json(self, gemini_llm):
        """Test parsing a valid JSON tool call."""
        text = '{"name": "get_conversation_history", "parameters": {"query": "find a good car"}}'
        result = gemini_llm._parse_tool_call_from_text(text)

        assert result is not None
        assert isinstance(result, ToolCall)
        assert result.name == "get_conversation_history"
        assert result.arguments == {"query": "find a good car"}

    def test_parse_tool_call_with_arguments_key(self, gemini_llm):
        """Test parsing JSON with 'arguments' instead of 'parameters'."""
        text = '{"name": "chat_reply", "arguments": {"message": "Hello!"}}'
        result = gemini_llm._parse_tool_call_from_text(text)

        assert result is not None
        assert result.name == "chat_reply"
        assert result.arguments == {"message": "Hello!"}

    def test_parse_tool_call_with_nested_json_string(self, gemini_llm):
        """Test parsing when parameters contains a stringified JSON."""
        text = '{"name": "get_conversation_history", "parameters": {"query": "{\\"type\\":\\"summary\\"}"}}'
        result = gemini_llm._parse_tool_call_from_text(text)

        assert result is not None
        assert result.name == "get_conversation_history"
        # The nested JSON should be parsed
        assert result.arguments == {"query": {"type": "summary"}}

    def test_parse_returns_none_for_regular_text(self, gemini_llm):
        """Test that regular text returns None."""
        text = "I can help you find a good car. What's your budget?"
        result = gemini_llm._parse_tool_call_from_text(text)

        assert result is None

    def test_parse_returns_none_for_invalid_json(self, gemini_llm):
        """Test that invalid JSON returns None."""
        text = '{"name": "incomplete'
        result = gemini_llm._parse_tool_call_from_text(text)

        assert result is None

    def test_parse_returns_none_for_json_without_name(self, gemini_llm):
        """Test that JSON without 'name' field returns None."""
        text = '{"parameters": {"query": "test"}}'
        result = gemini_llm._parse_tool_call_from_text(text)

        assert result is None

    def test_parse_handles_whitespace(self, gemini_llm):
        """Test parsing with leading/trailing whitespace."""
        text = '  \n{"name": "test_tool", "parameters": {"key": "value"}}  \n'
        result = gemini_llm._parse_tool_call_from_text(text)

        assert result is not None
        assert result.name == "test_tool"

    def test_parse_generates_unique_ids(self, gemini_llm):
        """Test that each parsed tool call gets a unique ID."""
        text = '{"name": "test_tool", "parameters": {}}'
        result1 = gemini_llm._parse_tool_call_from_text(text)
        result2 = gemini_llm._parse_tool_call_from_text(text)

        assert result1.id != result2.id

    def test_parse_empty_parameters(self, gemini_llm):
        """Test parsing with empty parameters."""
        text = '{"name": "simple_tool", "parameters": {}}'
        result = gemini_llm._parse_tool_call_from_text(text)

        assert result is not None
        assert result.name == "simple_tool"
        assert result.arguments == {}
