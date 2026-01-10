"""Base tool interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..context.models import ConversationContext


@dataclass
class ToolResult:
    """Result from tool execution."""

    success: bool
    data: Any
    error: Optional[str] = None
    message: Optional[str] = None


class BaseTool(ABC):
    """Abstract base class for all tools."""

    def __init__(self, name: str, description: str):
        """
        Initialize tool.

        Args:
            name: Tool name (used for registration)
            description: Tool description
        """
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(
        self, context: ConversationContext, **kwargs
    ) -> ToolResult:
        """
        Execute the tool with conversation context.

        Args:
            context: Conversation context with history and metadata
            **kwargs: Tool-specific parameters

        Returns:
            ToolResult with execution result
        """
        pass

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """
        Get tool schema for pydantic_ai registration.

        Returns:
            Dictionary with tool schema definition
        """
        pass

    def validate_input(self, **kwargs) -> bool:
        """
        Validate tool input parameters.

        Args:
            **kwargs: Input parameters

        Returns:
            True if valid, False otherwise
        """
        return True

    def get_name(self) -> str:
        """Get tool name."""
        return self.name

    def get_description(self) -> str:
        """Get tool description."""
        return self.description

