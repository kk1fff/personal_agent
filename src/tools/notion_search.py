"""Notion Search tool - searches index and fetches page content."""

import logging
from typing import Any, Dict, List, Optional

from ..context.models import ConversationContext
from ..memory.embeddings import EmbeddingGenerator
from ..memory.vector_store import VectorStore
from ..notion.client import NotionClient
from .base import BaseTool, ToolResult


class NotionSearchTool(BaseTool):
    """Tool for searching and reading Notion pages via semantic search."""

    COLLECTION_NAME = "notion_pages"

    def __init__(
        self,
        api_key: str,
        vector_store: VectorStore,
        embedding_generator: EmbeddingGenerator,
        default_results: int = 5,
    ):
        """
        Initialize Notion Search tool.

        Args:
            api_key: Notion API key
            vector_store: Vector store with indexed pages
            embedding_generator: Embedding generator for queries
            default_results: Default number of search results
        """
        super().__init__(
            name="notion_search",
            description=(
                "Search your Notion workspace and read page content. "
                "First searches the index for relevant pages, then optionally fetches "
                "the actual content. Use this to find information in your notes."
            ),
        )
        self.notion_client = NotionClient(api_key)
        self.vector_store = vector_store
        self.embedding_generator = embedding_generator
        self.default_results = default_results
        self.logger = logging.getLogger(__name__)

    async def execute(
        self, context: ConversationContext, **kwargs
    ) -> ToolResult:
        """
        Search Notion and optionally read page content.

        Args:
            context: Conversation context
            **kwargs:
                - query (str, required): Search query
                - read_page (bool, optional): If True, fetch full page content
                - page_id (str, optional): Specific page ID to read
                - max_results (int, optional): Max search results

        Returns:
            ToolResult with search results and/or page content
        """
        query = kwargs.get("query")
        read_page = kwargs.get("read_page", False)
        page_id = kwargs.get("page_id")
        max_results = kwargs.get("max_results", self.default_results)

        # If page_id is provided, directly fetch that page
        if page_id:
            try:
                page_content = await self._fetch_page_content(page_id)
                return ToolResult(
                    success=True,
                    data=page_content,
                    message=self._format_page_content(page_content),
                )
            except Exception as e:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Failed to fetch page {page_id}: {str(e)}",
                )

        # Query is required for search
        if not query:
            return ToolResult(
                success=False,
                data=None,
                error="Either 'query' or 'page_id' parameter is required",
            )

        # Search the index
        try:
            search_results = await self._search_index(query, max_results)
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Search failed: {str(e)}",
            )

        if not search_results:
            return ToolResult(
                success=True,
                data={"results": [], "count": 0},
                message="No matching pages found in Notion.",
            )

        # If read_page is True, fetch content of the best match
        if read_page and search_results:
            best_match = search_results[0]
            try:
                page_content = await self._fetch_page_content(
                    best_match["metadata"]["page_id"]
                )
                return ToolResult(
                    success=True,
                    data={
                        "page": page_content,
                        "other_matches": search_results[1:] if len(search_results) > 1 else [],
                    },
                    message=self._format_page_content(page_content),
                )
            except Exception as e:
                self.logger.warning(f"Failed to fetch page content: {e}")
                # Fall back to returning search results
                return ToolResult(
                    success=True,
                    data={"results": search_results, "count": len(search_results)},
                    message=self._format_search_results(search_results),
                )

        # Return search results only
        return ToolResult(
            success=True,
            data={"results": search_results, "count": len(search_results)},
            message=self._format_search_results(search_results),
        )

    async def _search_index(
        self, query: str, max_results: int
    ) -> List[Dict[str, Any]]:
        """
        Search the vector index for relevant pages.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            List of matching pages with metadata
        """
        # Generate embedding for query
        query_embedding = self.embedding_generator.generate_embedding(query)

        # Search vector store
        results = self.vector_store.search(
            query_embedding=query_embedding,
            n_results=max_results,
        )

        return results

    async def _fetch_page_content(self, page_id: str) -> Dict[str, Any]:
        """
        Fetch full content of a specific page.

        Args:
            page_id: Notion page ID

        Returns:
            Dictionary with page content and metadata
        """
        # Get page metadata
        page = self.notion_client.get_page(page_id)
        title = self.notion_client.get_page_title(page)

        # Get full content
        content = self.notion_client.get_page_content(page_id)

        # Get stored metadata from index if available
        stored = self.vector_store.get_by_id(page_id)
        path = stored.get("metadata", {}).get("path", title) if stored else title
        summary = stored.get("metadata", {}).get("summary", "") if stored else ""

        return {
            "page_id": page_id,
            "title": title,
            "path": path,
            "summary": summary,
            "content": content,
        }

    def _format_search_results(self, results: List[Dict[str, Any]]) -> str:
        """Format search results for display."""
        lines = [f"Found {len(results)} matching page(s):\n"]

        for i, result in enumerate(results, 1):
            metadata = result.get("metadata", {})
            title = metadata.get("title", "Untitled")
            path = metadata.get("path", title)
            summary = metadata.get("summary", "")
            page_id = metadata.get("page_id", "")

            lines.append(f"{i}. **{path}**")
            if summary:
                lines.append(f"   {summary}")
            lines.append(f"   Page ID: {page_id}")
            lines.append("")

        return "\n".join(lines)

    def _format_page_content(self, page_data: Dict[str, Any]) -> str:
        """Format page content for display."""
        lines = [
            f"# {page_data['title']}",
            f"Path: {page_data['path']}",
            "",
        ]

        if page_data.get("summary"):
            lines.extend([
                "**Summary:**",
                page_data["summary"],
                "",
            ])

        lines.extend([
            "**Content:**",
            page_data.get("content", ""),
        ])

        return "\n".join(lines)

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
                        "description": "Search query to find relevant Notion pages",
                    },
                    "read_page": {
                        "type": "boolean",
                        "description": "If True, fetch full content of the best matching page",
                        "default": False,
                    },
                    "page_id": {
                        "type": "string",
                        "description": "Specific page ID to read (bypasses search)",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of search results",
                        "default": 5,
                    },
                },
                "required": [],
            },
        }
