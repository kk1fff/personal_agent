"""Gemini LLM implementation."""

import uuid
from typing import Any, Dict, Iterator, List, Optional

import google.genai as genai

from .base import BaseLLM, LLMResponse, ToolCall


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

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
        )

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

