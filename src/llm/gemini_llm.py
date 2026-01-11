"""Gemini LLM implementation."""

from typing import Iterator, Optional

import google.genai as genai

from .base import BaseLLM


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
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs
    ) -> str:
        """
        Generate a response from Gemini.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt (used as system_instruction)
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            Generated text response
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

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )

        return response.text

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

