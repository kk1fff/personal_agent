"""Gemini LLM implementation."""

import json
import logging
import re
import uuid
from typing import Any, Dict, Iterator, List, Optional

import google.genai as genai

from .base import BaseLLM, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class GeminiLLM(BaseLLM):
    """Gemini LLM implementation for Google Gemini models."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-pro",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        safety_settings: Optional[dict] = None,
    ):
        """
        Initialize Gemini LLM.

        Args:
            api_key: Gemini API key
            model: Model name (e.g., "gemini-pro", "gemini-pro-vision")
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            safety_settings: Optional safety settings
        """
        self.api_key = api_key
        self.model_name = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.safety_settings = safety_settings

        # Initialize client with API key
        self.client = genai.Client(api_key=api_key)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate a response from Gemini.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt (used as system_instruction)
            tools: Optional list of tool definitions for function calling
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            LLMResponse with text and/or tool calls
        """
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        # Build config dict
        config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }

        # Add system instruction if provided
        if system_prompt:
            config["system_instruction"] = system_prompt

        # Add safety settings if provided
        if self.safety_settings:
            config["safety_settings"] = self.safety_settings

        # Add tools if provided
        if tools:
            # Convert to Gemini function declaration format
            function_declarations = []
            for tool in tools:
                function_declarations.append(
                    {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {}),
                    }
                )
            config["tools"] = [{"function_declarations": function_declarations}]

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )

        # Extract tool calls if present
        tool_calls = []
        text = None

        # Check for function calls in the response
        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, "content") and candidate.content:
                for part in candidate.content.parts:
                    if hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        tool_calls.append(
                            ToolCall(
                                id=str(uuid.uuid4()),
                                name=fc.name,
                                arguments=dict(fc.args) if fc.args else {},
                            )
                        )
                    elif hasattr(part, "text") and part.text:
                        text = part.text

        # Fallback to response.text if no parts found
        if text is None and not tool_calls:
            text = response.text

        # Fallback: Parse tool calls from text if no structured tool calls found
        # This handles cases where the model outputs JSON tool calls as text
        if not tool_calls and text:
            parsed_tool_call = self._parse_tool_call_from_text(text)
            if parsed_tool_call:
                tool_calls.append(parsed_tool_call)
                text = None  # Clear text since it was a tool call

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
        )

    def _parse_tool_call_from_text(self, text: str) -> Optional[ToolCall]:
        """
        Attempt to parse a tool call from text response.

        This handles cases where the model outputs a JSON tool call as text
        instead of using the proper function calling mechanism.

        Args:
            text: Text response from the model

        Returns:
            ToolCall if successfully parsed, None otherwise
        """
        text = text.strip()

        # Try to parse as JSON tool call format
        # Expected format: {"name": "tool_name", "parameters": {...}}
        try:
            # Handle text that might have extra content before/after JSON
            json_match = re.search(r'\{[^{}]*"name"[^{}]*"parameters"[^{}]*\{.*\}\s*\}', text, re.DOTALL)
            if json_match:
                text = json_match.group(0)

            data = json.loads(text)

            # Check for expected structure
            if isinstance(data, dict) and "name" in data:
                name = data["name"]
                parameters = data.get("parameters", data.get("arguments", {}))

                # Handle case where parameters is a string (nested JSON)
                if isinstance(parameters, str):
                    try:
                        parameters = json.loads(parameters)
                    except json.JSONDecodeError:
                        # If it's a string but not JSON, use it as-is
                        pass

                # Handle nested JSON strings within individual parameter values
                if isinstance(parameters, dict):
                    parameters = self._parse_nested_json_values(parameters)

                logger.debug(f"Parsed tool call from text: {name} with args {parameters}")

                return ToolCall(
                    id=str(uuid.uuid4()),
                    name=name,
                    arguments=parameters if isinstance(parameters, dict) else {"query": parameters},
                )
        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.debug(f"Failed to parse tool call from text: {e}")

        return None

    def _parse_nested_json_values(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively parse JSON strings within parameter values.

        Args:
            params: Dictionary of parameters

        Returns:
            Dictionary with JSON strings parsed into objects
        """
        result = {}
        for key, value in params.items():
            if isinstance(value, str):
                # Try to parse string values as JSON
                try:
                    parsed = json.loads(value)
                    # Recursively parse if it's a dict
                    if isinstance(parsed, dict):
                        result[key] = self._parse_nested_json_values(parsed)
                    else:
                        result[key] = parsed
                except json.JSONDecodeError:
                    result[key] = value
            elif isinstance(value, dict):
                result[key] = self._parse_nested_json_values(value)
            else:
                result[key] = value
        return result

    async def stream_generate(
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs
    ) -> Iterator[str]:
        """
        Generate a streaming response from Gemini.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt (used as system_instruction)
            **kwargs: Additional parameters

        Yields:
            Text chunks as they are generated
        """
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        # Build config dict
        config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }

        # Add system instruction if provided
        if system_prompt:
            config["system_instruction"] = system_prompt

        # Add safety settings if provided
        if self.safety_settings:
            config["safety_settings"] = self.safety_settings

        response_stream = self.client.models.generate_content_stream(
            model=self.model_name,
            contents=prompt,
            config=config,
        )

        for chunk in response_stream:
            if chunk.text:
                yield chunk.text

    def get_model_name(self) -> str:
        """Get the model name."""
        return self.model_name

