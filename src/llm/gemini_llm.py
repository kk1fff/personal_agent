"""Gemini LLM implementation."""

from typing import Iterator, Optional

import google.generativeai as genai

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

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=model,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
            safety_settings=safety_settings,
        )

    async def generate(
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs
    ) -> str:
        """
        Generate a response from Gemini.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt (prepended to prompt)
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            Generated text response
        """
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        # Update generation config if parameters changed
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }

        response = self.model.generate_content(
            full_prompt,
            generation_config=generation_config,
        )

        return response.text

    async def stream_generate(
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs
    ) -> Iterator[str]:
        """
        Generate a streaming response from Gemini.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Yields:
            Text chunks as they are generated
        """
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }

        response = self.model.generate_content(
            full_prompt,
            generation_config=generation_config,
            stream=True,
        )

        for chunk in response:
            if chunk.text:
                yield chunk.text

    def get_model_name(self) -> str:
        """Get the model name."""
        return self.model_name

