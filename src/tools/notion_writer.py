"""Notion Writer tool for writing to Notion."""

from typing import Any, Dict

from notion_client import Client

from .base import BaseTool, ToolResult
from ..context.models import ConversationContext


class NotionWriterTool(BaseTool):
    """Tool for writing content to Notion pages."""

    def __init__(self, api_key: str):
        """
        Initialize Notion Writer tool.

        Args:
            api_key: Notion API key
        """
        super().__init__(
            name="notion_writer",
            description="Write content to a Notion page. Can create new pages or update existing ones.",
        )
        self.client = Client(auth=api_key)

    async def execute(
        self, context: ConversationContext, **kwargs
    ) -> ToolResult:
        """
        Write to a Notion page.

        Args:
            context: Conversation context
            **kwargs: Must contain:
                - 'parent_id' (str): Parent page/database ID
                - 'title' (str): Page title
                - 'content' (str, optional): Page content

        Returns:
            ToolResult with created/updated page info
        """
        if "parent_id" not in kwargs:
            return ToolResult(
                success=False,
                data=None,
                error="Missing required parameter: parent_id",
            )

        if "title" not in kwargs:
            return ToolResult(
                success=False,
                data=None,
                error="Missing required parameter: title",
            )

        parent_id = kwargs["parent_id"]
        title = kwargs["title"]
        content = kwargs.get("content", "")

        # Extract page ID from URL if needed
        if parent_id.startswith("http"):
            parts = parent_id.split("/")
            parent_id = parts[-1].split("?")[0].replace("-", "")

        try:
            # Create a new page
            new_page = self.client.pages.create(
                parent={"page_id": parent_id},
                properties={
                    "title": {
                        "title": [
                            {
                                "text": {
                                    "content": title,
                                }
                            }
                        ]
                    }
                },
            )

            page_id = new_page["id"]

            # Add content if provided
            if content:
                # Split content into paragraphs
                paragraphs = content.split("\n\n")
                children = []
                for para in paragraphs:
                    if para.strip():
                        children.append(
                            {
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {
                                    "rich_text": [
                                        {
                                            "type": "text",
                                            "text": {
                                                "content": para,
                                            }
                                        }
                                    ]
                                },
                            }
                        )

                if children:
                    self.client.blocks.children.append(page_id, children=children)

            return ToolResult(
                success=True,
                data={
                    "page_id": page_id,
                    "title": title,
                    "created": True,
                },
                message=f"Successfully created Notion page '{title}'",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to write to Notion: {str(e)}",
            )

    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema for pydantic_ai."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "parent_id": {
                        "type": "string",
                        "description": "Parent page or database ID where to create the page",
                    },
                    "title": {
                        "type": "string",
                        "description": "Title of the page",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to add to the page (optional)",
                    },
                },
                "required": ["parent_id", "title"],
            },
        }

