"""Memory Agent-as-a-Tool wrapper."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .base_agent_tool import BaseAgentTool


class MemoryQuery(BaseModel):
    """Structured request for Memory specialist.

    This model defines the interface between the Dispatcher
    and the Memory specialist agent.
    """

    query: str = Field(
        ...,
        description="What to search for in conversation history"
    )
    mode: Literal["recent", "smart", "llm"] = Field(
        default="llm",
        description=(
            "'recent' for last N messages, "
            "'smart' for session-based clustering, "
            "'llm' for intelligent summarization"
        )
    )
    max_messages: Optional[int] = Field(
        default=None,
        ge=1,
        le=50,
        description="Maximum number of messages to retrieve"
    )


class MemoryAgentTool(BaseAgentTool):
    """Tool wrapper for Memory specialist agent.

    Exposes the Memory specialist to the Dispatcher as a callable tool,
    using the MemoryQuery model for structured hand-off.
    """

    request_model = MemoryQuery

    def __init__(self, memory_specialist: "MemorySpecialist"):
        """Initialize Memory agent tool.

        Args:
            memory_specialist: The Memory specialist agent instance
        """
        super().__init__(
            agent=memory_specialist,
            request_model=MemoryQuery,
        )
