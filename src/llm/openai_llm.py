"""OpenAI LLM implementation."""

from typing import Iterator, Optional

from openai import AsyncOpenAI

from .base import BaseLLM


class OpenAILLM(BaseLLM):
    """OpenAI LLM implementation for ChatGPT/GPT models."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        organization_id: Optional[str] = None,
    ):
        """
        Initialize OpenAI LLM.

        Args:
            api_key: OpenAI API key
            model: Model name (e.g., "gpt-3.5-turbo", "gpt-4")
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            organization_id: Optional organization ID
        """
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.organization_id = organization_id

        self.client = AsyncOpenAI(
            api_key=api_key,
            organization=organization_id,
        )

    async def generate(
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs
    ) -> str:
        """
        Generate a response from OpenAI.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            Generated text response
        """
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        model = kwargs.get("model", self.model)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content or ""

    async def stream_generate(
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs
    ) -> Iterator[str]:
        """
        Generate a streaming response from OpenAI.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Yields:
            Text chunks as they are generated
        """
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        model = kwargs.get("model", self.model)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def get_model_name(self) -> str:
        """Get the model name."""
        return self.model

