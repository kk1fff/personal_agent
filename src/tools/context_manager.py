"""Context Manager tool for retrieving conversation history."""

from typing import Any, Dict

from .base import BaseTool, ToolResult
from ..context.models import ConversationContext


class ContextManagerTool(BaseTool):
    """Tool for retrieving previous conversation messages."""

    def __init__(
        self,
        context_manager,
    ):
        """
        Initialize Context Manager tool.

        Args:
            context_manager: ConversationContextManager instance
        """
        super().__init__(
            name="get_conversation_history",
            description=(
                "Retrieve a summarized context of the conversation history "
                "relevant to a specific query. Use this tool when you need "
                "context from previous messages to answer the user's request. "
                "DO NOT CALL THIS TOOL MORE THEN ONCE"
            ),
        )
        self.context_manager = context_manager

    async def execute(
        self, context: ConversationContext, **kwargs
    ) -> ToolResult:
        """
        Retrieve conversation history summary.

        Args:
            context: Current conversation context
            **kwargs:
                - query: user query (required)

        Returns:
            ToolResult with summarized conversation context
        """
        query = kwargs.get("query")
        if not query:
            return ToolResult(
                success=False,
                data=None,
                error="Query parameter is required"
            )

        try:
            summary, count = await self.context_manager.get_llm_context(
                chat_id=context.chat_id,
                user_id=context.user_id,
                query=query,
            )

            return ToolResult(
                success=True,
                data={
                    "count": count,
                    "summary": summary
                },
                message=f"Context Summary (based on {count} messages):\n\n{summary}"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to generate LLM context: {str(e)}"
            )

    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema for pydantic_ai."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The user's current request/query. Required to generate relevant summary.",
                    }
                },
                "required": ["query"],
            },
        }

