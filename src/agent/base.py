"""Base classes for multi-agent orchestrator pattern."""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from ..llm.base import BaseLLM
from ..tools.base import BaseTool


@dataclass
class AgentContext:
    """Unified context passed to all agents.

    This replaces ConversationContext for the orchestrator pattern,
    providing a cleaner interface with trace support for debugging.
    """

    # Session/User identification
    chat_id: int
    user_id: int
    session_id: str

    # Message history (passed from dispatcher to specialists)
    message_history: List[Dict[str, str]] = field(default_factory=list)

    # Metadata for additional context (timezone, trace, etc.)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Trace IDs for debugging/SVG generation
    parent_trace_id: Optional[str] = None
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def get_trace(self) -> Optional["RequestTrace"]:
        """Get the request trace from metadata if present."""
        return self.metadata.get("trace")

    def with_child_trace(self) -> "AgentContext":
        """Create a child context with a new trace ID for delegation."""
        return AgentContext(
            chat_id=self.chat_id,
            user_id=self.user_id,
            session_id=self.session_id,
            message_history=self.message_history.copy(),
            metadata=self.metadata.copy(),
            parent_trace_id=self.trace_id,
            trace_id=str(uuid.uuid4()),
        )


class AgentResult(BaseModel):
    """Standardized result from any agent.

    All agents return this structured result, enabling the dispatcher
    to predictably parse specialist responses.
    """

    success: bool
    response_text: str
    structured_data: Optional[Dict[str, Any]] = None
    agent_name: str
    trace_id: str

    # For debugging
    tool_calls_made: List[str] = []
    processing_time_ms: float = 0


class BaseAgent(ABC):
    """Abstract base class for all agents (Dispatcher and Specialists).

    Each agent receives a unified context but unique tools.
    The Dispatcher sees Agent-as-Tool wrappers, while Specialists
    see their domain-specific tools.
    """

    def __init__(
        self,
        name: str,
        description: str,
        llm: BaseLLM,
        system_prompt: str,
        tools: Optional[List[BaseTool]] = None,
    ):
        """Initialize agent.

        Args:
            name: Agent identifier (e.g., "notion_specialist")
            description: Human-readable description for registry
            llm: LLM instance for processing
            system_prompt: Base system prompt (may be augmented dynamically)
            tools: List of tools available to this agent
        """
        self.name = name
        self.description = description
        self.llm = llm
        self._base_system_prompt = system_prompt
        self._tools = tools or []

    @abstractmethod
    async def process(
        self,
        message: str,
        context: AgentContext
    ) -> AgentResult:
        """Process a message and return structured result.

        Args:
            message: User message or delegated query
            context: Unified agent context

        Returns:
            AgentResult with response and metadata
        """
        pass

    @abstractmethod
    def get_system_prompt(self, context: AgentContext) -> str:
        """Get system prompt with injected context.

        The prompt may be dynamically generated based on context,
        such as including agent descriptions for the dispatcher.

        Args:
            context: Agent context for dynamic prompt generation

        Returns:
            Complete system prompt string
        """
        pass

    def get_tools(self) -> List[BaseTool]:
        """Get tools available to this agent."""
        return self._tools

    def get_name(self) -> str:
        """Get agent identifier."""
        return self.name

    def get_description(self) -> str:
        """Get human-readable description."""
        return self.description
