"""Chat Reply tool for sending messages back to Telegram."""

from typing import Any, Dict

from .base import BaseTool, ToolResult
from ..context.models import ConversationContext


class ChatReplyTool(BaseTool):
    """Tool for sending replies back to Telegram chat."""

    def __init__(self, send_message_callback):
        """
        Initialize Chat Reply tool.

        Args:
            send_message_callback: Async function(chat_id: int, text: str) -> None
        """
        super().__init__(
            name="chat_reply",
            description="Send a message reply back to the Telegram chat. Use this to respond to the user.",
        )
        self.send_message = send_message_callback

    async def execute(
        self, context: ConversationContext, **kwargs
    ) -> ToolResult:
        """
        Send a message reply.

        Args:
            context: Conversation context
            **kwargs: Must contain 'message' (str) - the message to send

        Returns:
            ToolResult indicating success or failure
        """
        if "message" not in kwargs:
            return ToolResult(
                success=False,
                data=None,
                error="Missing required parameter: message",
            )

        message_text = kwargs["message"]
        if not isinstance(message_text, str) or not message_text.strip():
            return ToolResult(
                success=False,
                data=None,
                error="Message must be a non-empty string",
            )

        try:
            await self.send_message(context.chat_id, message_text)
            return ToolResult(
                success=True,
                data={"sent": True, "chat_id": context.chat_id},
                message=f"Message sent to chat {context.chat_id}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to send message: {str(e)}",
            )

    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema for pydantic_ai."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message text to send to the user",
                    }
                },
                "required": ["message"],
            },
        }

