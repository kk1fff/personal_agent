"""Context Manager tool for retrieving conversation history."""

from typing import Any, Dict

from .base import BaseTool, ToolResult
from ..context.models import ConversationContext


class ContextManagerTool(BaseTool):
    """Tool for retrieving previous conversation messages."""

    def __init__(
        self,
        context_manager,
        max_history: int = 5,
        time_gap_threshold_minutes: int = 60,
    ):
        """
        Initialize Context Manager tool.

        Args:
            context_manager: ConversationContextManager instance
            max_history: Maximum number of previous messages agent can request
            time_gap_threshold_minutes: Time gap threshold for session detection
        """
        super().__init__(
            name="get_conversation_history",
            description=f"Retrieve previous messages from the conversation history. "
                       f"Two modes available: "
                       f"'recent' returns the last N messages (up to {max_history}). "
                       f"'smart' uses time-gap clustering to return messages from the current session only. "
                       f"Use 'smart' mode when you need to understand the current conversation context "
                       f"(e.g., user says 'what do you think?' without clear context). "
                       f"Use 'recent' for a quick lookback at a specific number of messages.",
        )
        self.context_manager = context_manager
        self.max_history = max_history
        self.time_gap_threshold_minutes = time_gap_threshold_minutes

    async def execute(
        self, context: ConversationContext, **kwargs
    ) -> ToolResult:
        """
        Retrieve conversation history.

        Args:
            context: Current conversation context
            **kwargs:
                - mode: "recent" (default) or "smart"
                - count: number of messages to retrieve (for "recent" mode only)

        Returns:
            ToolResult with formatted conversation history
        """
        mode = kwargs.get("mode", "recent")

        if mode == "smart":
            return await self._execute_smart_mode(context)
        else:
            return await self._execute_recent_mode(context, kwargs)

    async def _execute_recent_mode(
        self, context: ConversationContext, kwargs: dict
    ) -> ToolResult:
        """Execute in recent mode (original behavior)."""
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
                data={
                    "count": len(messages),
                    "messages": formatted_messages,
                    "mode": "recent",
                },
                message=f"Retrieved {len(messages)} recent message(s):\n\n{history_text}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to retrieve conversation history: {str(e)}"
            )

    async def _execute_smart_mode(
        self, context: ConversationContext
    ) -> ToolResult:
        """Execute in smart mode (time-gap clustering)."""
        try:
            smart_context, session_count = await self.context_manager.get_smart_context(
                chat_id=context.chat_id,
                user_id=context.user_id,
            )

            formatted_messages = []
            for msg in smart_context.messages:
                role = "User" if msg.role == "user" else "Assistant"
                formatted_messages.append(f"{role}: {msg.message_text}")

            history_text = "\n".join(formatted_messages)

            if session_count == 0:
                return ToolResult(
                    success=True,
                    data={
                        "count": 0,
                        "messages": [],
                        "mode": "smart",
                        "session_detected": False,
                    },
                    message="No recent session messages found. The conversation may have been idle."
                )

            return ToolResult(
                success=True,
                data={
                    "count": session_count,
                    "messages": formatted_messages,
                    "mode": "smart",
                    "session_detected": True,
                },
                message=f"Retrieved {session_count} message(s) from current session:\n\n{history_text}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to retrieve smart context: {str(e)}"
            )

    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema for pydantic_ai."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["recent", "smart"],
                        "description": "Context retrieval mode: 'recent' for last N messages, 'smart' for current session using time-gap clustering",
                        "default": "recent",
                    },
                    "count": {
                        "type": "integer",
                        "description": f"Number of previous messages to retrieve (1 to {self.max_history}). Only used in 'recent' mode.",
                        "minimum": 1,
                        "maximum": self.max_history,
                    }
                },
                "required": [],  # All parameters are optional with defaults
            },
        }
