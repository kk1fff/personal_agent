"""Ollama LLM implementation."""

import logging
from typing import Iterator, Optional

import ollama

from .base import BaseLLM

logger = logging.getLogger(__name__)


class OllamaLLM(BaseLLM):
    """Ollama LLM implementation for local models."""

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        context_window: Optional[int] = None,
    ):
        """
        Initialize Ollama LLM.

        Args:
            model: Model name (e.g., "llama2", "mistral")
            base_url: Ollama server base URL
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            context_window: Context window size
        """
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.context_window = context_window

        # Set base URL for ollama client
        ollama.Client(host=base_url)

    async def generate(
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs
    ) -> str:
        """
        Generate a response from Ollama.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            Generated text response
        """
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = ollama.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            )
            return response["message"]["content"]
        except Exception as e:
            logger.error(
                f"Ollama LLM generation failed - Model: {self.model}, "
                f"Base URL: {self.base_url}, Error: {e}",
                exc_info=True
            )
            raise

    async def stream_generate(
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs
    ) -> Iterator[str]:
        """
        Generate a streaming response from Ollama.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Yields:
            Text chunks as they are generated
        """
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = ollama.chat(
            model=self.model,
            messages=messages,
            stream=True,
            options={
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        )

        for chunk in stream:
            if "message" in chunk and "content" in chunk["message"]:
                yield chunk["message"]["content"]

    def get_model_name(self) -> str:
        """Get the model name."""
        return self.model

    async def validate(self) -> None:
        """
        Validate that the LLM is accessible and the model exists.

        Raises:
            Exception: If validation fails (model not found, server unreachable, etc.)
        """
        try:
            # Make a simple test call to verify model exists
            logger.debug(f"Validating Ollama model: {self.model} at {self.base_url}")
            await self.generate(
                "Hello",
                system_prompt="You are a helpful assistant. Respond with just 'Hi'.",
            )
            logger.info(f"✓ LLM validation successful: {self.model}")
        except Exception as e:
            logger.error(f"✗ LLM validation failed: {e}")
            raise

