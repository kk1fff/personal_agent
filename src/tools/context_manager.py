"""Context Manager tool for retrieving conversation history."""

from typing import Any, Dict

from .base import BaseTool, ToolResult
from ..context.models import ConversationContext


class ContextManagerTool(BaseTool):
    """Tool for retrieving previous conversation messages."""

    def __init__(self, context_manager, max_history: int = 5):
        """
        Initialize Context Manager tool.

        Args:
            context_manager: ConversationContextManager instance
            max_history: Maximum number of previous messages agent can request
        """
        super().__init__(
            name="get_conversation_history",
            description=f"Retrieve previous messages from the conversation history. "
                       f"You can request up to {max_history} previous messages. "
                       f"Use this tool when you need context from earlier in the conversation.",
        )
        self.context_manager = context_manager
        self.max_history = max_history

    async def execute(
        self, context: ConversationContext, **kwargs
    ) -> ToolResult:
        """
        Retrieve conversation history.

        Args:
            context: Current conversation context
            **kwargs: Must contain 'count' (int) - number of messages to retrieve

        Returns:
            ToolResult with formatted conversation history
        """
        # Get requested count, default to max_history
        count = kwargs.get("count", self.max_history)

        # Validate count
        if not isinstance(count, int) or count < 1:
            return ToolResult(
                success=False,
                data=None,
                error="Count must be a positive integer"
            )

        # Enforce max_history limit
        if count > self.max_history:
            count = self.max_history

        try:
            # Retrieve messages from database
            messages = await self.context_manager.get_recent_messages(
                chat_id=context.chat_id,
                limit=count
            )

            # Format messages for agent (content only, no metadata)
            formatted_messages = []
            for msg in messages:
                role = "User" if msg.role == "user" else "Assistant"
                formatted_messages.append(f"{role}: {msg.message_text}")

            history_text = "\n".join(formatted_messages)

            return ToolResult(
                success=True,
                data={"count": len(messages), "messages": formatted_messages},
                message=f"Retrieved {len(messages)} previous message(s):\n\n{history_text}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to retrieve conversation history: {str(e)}"
            )

    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema for pydantic_ai."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": f"Number of previous messages to retrieve (1 to {self.max_history})",
                        "minimum": 1,
                        "maximum": self.max_history,
                    }
                },
                "required": ["count"],
            },
        }
