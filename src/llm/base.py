"""Base LLM interface."""

from abc import ABC, abstractmethod
from typing import Iterator, Optional


class BaseLLM(ABC):
    """Abstract base class for LLM implementations."""

    @abstractmethod
    async def generate(
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs
    ) -> str:
        """
        Generate a response from the LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional provider-specific parameters

        Returns:
            Generated text response
        """
        pass

    @abstractmethod
    async def stream_generate(
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs
    ) -> Iterator[str]:
        """
        Generate a streaming response from the LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional provider-specific parameters

        Yields:
            Text chunks as they are generated
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """
        Get the model name being used.

        Returns:
            Model name string
        """
        pass

