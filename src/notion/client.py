"""Notion API client wrapper with traversal support."""

import logging
import time
from typing import Any, Dict, Iterator, List, Optional

from notion_client import Client

from .models import NotionBlock


class NotionClient:
    """Enhanced Notion API client with traversal and content extraction."""

    def __init__(self, api_key: str, rate_limit_delay: float = 0.35):
        """
        Initialize Notion client.

        Args:
            api_key: Notion integration API key
            rate_limit_delay: Delay between API calls (seconds) to avoid rate limits
        """
        self.client = Client(auth=api_key)
        self.rate_limit_delay = rate_limit_delay
        self.logger = logging.getLogger(__name__)

    def _rate_limit(self) -> None:
        """Apply rate limiting delay between API calls."""
        if self.rate_limit_delay > 0:
            time.sleep(self.rate_limit_delay)

    def get_page(self, page_id: str) -> Dict[str, Any]:
        """
        Fetch a single page by ID.

        Args:
            page_id: Notion page ID

        Returns:
            Page object from Notion API
        """
        self._rate_limit()
        return self.client.pages.retrieve(page_id=page_id)

    def get_page_title(self, page: Dict[str, Any]) -> str:
        """
        Extract title from page properties.

        Args:
            page: Page object from Notion API

        Returns:
            Page title as string
        """
        properties = page.get("properties", {})

        # Try common title property names
        for prop_name in ["title", "Title", "Name", "name"]:
            if prop_name in properties:
                prop = properties[prop_name]
                if prop.get("type") == "title":
                    title_array = prop.get("title", [])
                    if title_array:
                        return "".join(
                            t.get("plain_text", "") for t in title_array
                        )

        # Fallback: check all properties for title type
        for prop in properties.values():
            if prop.get("type") == "title":
                title_array = prop.get("title", [])
                if title_array:
                    return "".join(t.get("plain_text", "") for t in title_array)

        return "Untitled"

    def get_blocks(self, block_id: str) -> List[NotionBlock]:
        """
        Fetch all blocks under a page or block, handling pagination.

        Args:
            block_id: Page ID or block ID

        Returns:
            List of NotionBlock objects
        """
        blocks = []
        cursor = None

        while True:
            self._rate_limit()
            response = self.client.blocks.children.list(
                block_id=block_id, start_cursor=cursor, page_size=100
            )

            for block in response.get("results", []):
                content = self._extract_block_content(block)
                blocks.append(
                    NotionBlock(
                        block_id=block["id"],
                        block_type=block["type"],
                        content=content,
                        has_children=block.get("has_children", False),
                    )
                )

            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")

        return blocks

    def _extract_block_content(self, block: Dict[str, Any]) -> str:
        """
        Extract text content from a block.

        Args:
            block: Block object from Notion API

        Returns:
            Plain text content
        """
        block_type = block.get("type", "")
        block_data = block.get(block_type, {})

        # Handle special block types first (before generic rich_text handling)
        if block_type == "code":
            code_text = "".join(
                t.get("plain_text", "") for t in block_data.get("rich_text", [])
            )
            language = block_data.get("language", "")
            return f"```{language}\n{code_text}\n```"

        # Handle rich text blocks
        if "rich_text" in block_data:
            return "".join(
                t.get("plain_text", "") for t in block_data.get("rich_text", [])
            )

        # Handle other special block types
        if block_type == "child_page":
            return f"[Page: {block_data.get('title', '')}]"
        elif block_type == "child_database":
            return f"[Database: {block_data.get('title', '')}]"
        elif block_type == "image":
            caption = block_data.get("caption", [])
            caption_text = "".join(t.get("plain_text", "") for t in caption)
            return f"[Image: {caption_text}]" if caption_text else "[Image]"
        elif block_type == "code":
            code_text = "".join(
                t.get("plain_text", "") for t in block_data.get("rich_text", [])
            )
            language = block_data.get("language", "")
            return f"```{language}\n{code_text}\n```"
        elif block_type == "equation":
            return f"[Equation: {block_data.get('expression', '')}]"
        elif block_type == "table_of_contents":
            return "[Table of Contents]"
        elif block_type == "divider":
            return "---"
        elif block_type == "bookmark":
            url = block_data.get("url", "")
            return f"[Bookmark: {url}]"

        return ""

    def get_page_content(self, page_id: str, include_children: bool = True) -> str:
        """
        Extract all text content from a page as plain text.

        Args:
            page_id: Notion page ID
            include_children: Whether to recursively fetch child blocks

        Returns:
            Plain text content of the page
        """
        content_parts = []

        def process_blocks(block_id: str, depth: int = 0) -> None:
            if depth > 10:  # Prevent infinite recursion
                return

            blocks = self.get_blocks(block_id)
            for block in blocks:
                if block.content:
                    # Add indentation for nested blocks
                    indent = "  " * depth
                    content_parts.append(f"{indent}{block.content}")

                # Recursively process child blocks
                if include_children and block.has_children:
                    process_blocks(block.block_id, depth + 1)

        process_blocks(page_id)
        return "\n".join(content_parts)

    def get_child_pages(self, page_id: str) -> List[str]:
        """
        Get IDs of all child pages under a parent page.

        Args:
            page_id: Parent page ID

        Returns:
            List of child page IDs
        """
        child_page_ids = []
        blocks = self.get_blocks(page_id)

        for block in blocks:
            if block.block_type == "child_page":
                child_page_ids.append(block.block_id)
            elif block.block_type == "child_database":
                # Include databases as they contain pages
                child_page_ids.append(block.block_id)

        return child_page_ids

    def query_database(
        self, database_id: str, page_size: int = 100
    ) -> Iterator[Dict[str, Any]]:
        """
        Query a database and yield all pages, handling pagination.

        Args:
            database_id: Database ID
            page_size: Number of results per page

        Yields:
            Page objects from the database
        """
        cursor = None

        while True:
            self._rate_limit()
            response = self.client.databases.query(
                database_id=database_id,
                start_cursor=cursor,
                page_size=page_size,
            )

            for page in response.get("results", []):
                yield page

            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")

    def get_database(self, database_id: str) -> Dict[str, Any]:
        """
        Get database metadata.

        Args:
            database_id: Database ID

        Returns:
            Database object from Notion API
        """
        self._rate_limit()
        return self.client.databases.retrieve(database_id=database_id)

    def get_database_title(self, database: Dict[str, Any]) -> str:
        """
        Extract title from database.

        Args:
            database: Database object from Notion API

        Returns:
            Database title as string
        """
        title_array = database.get("title", [])
        if title_array:
            return "".join(t.get("plain_text", "") for t in title_array)
        return "Untitled Database"

    def is_database(self, object_id: str) -> bool:
        """
        Check if an object ID is a database.

        Args:
            object_id: Notion object ID

        Returns:
            True if it's a database, False otherwise
        """
        try:
            self._rate_limit()
            self.client.databases.retrieve(database_id=object_id)
            return True
        except Exception:
            return False
