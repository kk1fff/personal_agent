"""Notion Reader tool for reading from Notion."""

from typing import Any, Dict, Optional

from notion_client import Client

from .base import BaseTool, ToolResult
from ..context.models import ConversationContext


class NotionReaderTool(BaseTool):
    """Tool for reading content from Notion pages."""

    def __init__(self, api_key: str):
        """
        Initialize Notion Reader tool.

        Args:
            api_key: Notion API key
        """
        super().__init__(
            name="notion_reader",
            description="Read content from a Notion page by page ID or URL. Returns the page content and properties.",
        )
        self.client = Client(auth=api_key)

    async def execute(
        self, context: ConversationContext, **kwargs
    ) -> ToolResult:
        """
        Read a Notion page.

        Args:
            context: Conversation context
            **kwargs: Must contain 'page_id' (str) - Notion page ID or URL

        Returns:
            ToolResult with page content
        """
        if "page_id" not in kwargs:
            return ToolResult(
                success=False,
                data=None,
                error="Missing required parameter: page_id",
            )

        page_id = kwargs["page_id"]
        if not isinstance(page_id, str):
            return ToolResult(
                success=False,
                data=None,
                error="page_id must be a string",
            )

        # Extract page ID from URL if needed
        if page_id.startswith("http"):
            # Extract ID from Notion URL
            parts = page_id.split("/")
            page_id = parts[-1].split("?")[0].replace("-", "")

        try:
            page = self.client.pages.retrieve(page_id)
            blocks = self.client.blocks.children.list(page_id)

            # Extract text content from blocks
            content = []
            for block in blocks.get("results", []):
                block_type = block.get("type")
                if block_type == "paragraph":
                    text = block.get("paragraph", {}).get("rich_text", [])
                    if text:
                        content.append(" ".join([t.get("plain_text", "") for t in text]))
                elif block_type == "heading_1":
                    text = block.get("heading_1", {}).get("rich_text", [])
                    if text:
                        content.append("# " + " ".join([t.get("plain_text", "") for t in text]))
                elif block_type == "heading_2":
                    text = block.get("heading_2", {}).get("rich_text", [])
                    if text:
                        content.append("## " + " ".join([t.get("plain_text", "") for t in text]))

            return ToolResult(
                success=True,
                data={
                    "page_id": page_id,
                    "title": page.get("properties", {}).get("title", {}).get("title", [{}])[0].get("plain_text", ""),
                    "content": "\n".join(content),
                    "properties": page.get("properties", {}),
                },
                message=f"Successfully read Notion page {page_id}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to read Notion page: {str(e)}",
            )

    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema for pydantic_ai."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "string",
                        "description": "Notion page ID or URL",
                    }
                },
                "required": ["page_id"],
            },
        }

