"""Base LLM interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional

if TYPE_CHECKING:
    from ..debug.trace import RequestTrace


@dataclass
class ToolCall:
    """Represents a tool call from the LLM."""

    id: str
    name: str
    arguments: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
        }


@dataclass
class LLMResponse:
    """Response from LLM that may contain text and/or tool calls."""

    text: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)


class BaseLLM(ABC):
    """Abstract base class for LLM implementations.

    All LLM calls are automatically traced when a trace is set via set_trace().
    This ensures consistent logging regardless of how the LLM is called.
    """

    def __init__(self):
        """Initialize base LLM with trace support."""
        self._trace: Optional["RequestTrace"] = None
        self._source_name: str = "llm"

    def set_trace(self, trace: Optional["RequestTrace"], source_name: str = "llm"):
        """Set the request trace for recording LLM calls.

        Args:
            trace: RequestTrace instance or None to disable tracing
            source_name: Name of the calling component for trace attribution
        """
        self._trace = trace
        self._source_name = source_name

    def clear_trace(self):
        """Clear the current trace."""
        self._trace = None
        self._source_name = "llm"

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate a response from the LLM with automatic trace recording.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            tools: Optional list of tool definitions for function calling
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse with text and/or tool calls
        """
        # Record request if trace is set
        if self._trace:
            from ..debug.trace import TraceEventType
            self._trace.add_event(
                TraceEventType.LLM_REQUEST,
                source=self._source_name,
                target=self.get_model_name(),
                content_summary=f"LLM request (prompt length: {len(prompt)})",
                metadata={
                    "model": self.get_model_name(),
                    "prompt": prompt,
                    "system_prompt": system_prompt if system_prompt else "",
                    "tools": tools,
                }
            )

        # Call implementation
        response = await self._generate_impl(prompt, system_prompt, tools, **kwargs)

        # Record response if trace is set
        if self._trace:
            from ..debug.trace import TraceEventType
            self._trace.add_event(
                TraceEventType.LLM_RESPONSE,
                source=self.get_model_name(),
                target=self._source_name,
                content_summary=f"LLM response (length: {len(response.text or '')})",
                metadata={
                    "tool_calls": [tc.to_dict() for tc in response.tool_calls],
                    "response": response.text,
                }
            )

        return response

    @abstractmethod
    async def _generate_impl(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Implementation of generate. Subclasses must implement this.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            tools: Optional list of tool definitions for function calling
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse with text and/or tool calls
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

    async def validate(self) -> None:
        """
        Validate that the LLM is accessible and working.

        Default implementation makes a simple test call.
        Subclasses can override for more specific validation.

        Raises:
            Exception: If validation fails
        """
        # Default implementation: make a simple test call
        await self.generate("Hello", system_prompt="Respond with just 'Hi'.")

