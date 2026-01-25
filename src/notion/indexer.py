"""Notion workspace indexer."""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from ..config.config_schema import NotionWorkspaceConfig
from ..llm.base import BaseLLM
from ..memory.embeddings import EmbeddingGenerator
from ..memory.vector_store import VectorStore
from .client import NotionClient
from .models import IndexingStats, NotionPage, TraversalProgress
from .traversal import WorkspaceTraverser


class NotionIndexer:
    """Indexes Notion pages into vector store with LLM summaries."""

    COLLECTION_NAME = "notion_pages"
    MAX_CONTENT_LENGTH = 8000  # Max chars for summary generation
    DEFAULT_INFO_PATH = "data/notion/info.json"

    WORKSPACE_SUMMARY_PROMPT = """You are analyzing a user's Notion workspace. Based on the following indexed pages,
provide a brief summary (2-3 sentences) of what types of content the user stores in their Notion.
Focus on the main categories and topics. Be concise.

Workspace: {workspace_name}
Number of pages: {page_count}

Indexed pages:
{pages}

Summary:"""

    def __init__(
        self,
        notion_client: NotionClient,
        llm: BaseLLM,
        vector_store: VectorStore,
        embedding_generator: EmbeddingGenerator,
        summary_prompt_template: Optional[str] = None,
    ):
        """
        Initialize indexer.

        Args:
            notion_client: Notion API client
            llm: LLM for generating summaries
            vector_store: Vector store for storing embeddings
            embedding_generator: Embedding generator
            summary_prompt_template: Optional custom prompt for summaries
        """
        self.notion_client = notion_client
        self.llm = llm
        self.vector_store = vector_store
        self.embedding_generator = embedding_generator
        self.logger = logging.getLogger(__name__)

        self.summary_prompt = summary_prompt_template or self._default_summary_prompt()

    def _default_summary_prompt(self) -> str:
        """Get default summary prompt template."""
        return """Summarize the following Notion page content in 2-3 sentences.
Focus on the main topic and key information. Be concise and informative.

Page Title: {title}
Page Path: {path}

Content:
{content}

Summary:"""

    async def index_workspace(
        self,
        workspace_config: NotionWorkspaceConfig,
        force_reindex: bool = False,
        progress_callback: Optional[Callable[[TraversalProgress], None]] = None,
    ) -> IndexingStats:
        """
        Index all pages in a workspace.

        Args:
            workspace_config: Workspace configuration
            force_reindex: If True, reindex all pages even if unchanged
            progress_callback: Optional callback for progress updates

        Returns:
            IndexingStats with indexing statistics
        """
        stats = IndexingStats()
        indexed_page_ids: Set[str] = set()

        traverser = WorkspaceTraverser(
            client=self.notion_client,
            workspace_config=workspace_config,
            progress_callback=progress_callback,
        )

        self.logger.info(f"Starting indexing for workspace: {workspace_config.name}")

        for page_id, title, path in traverser.traverse():
            try:
                indexed_page = await self.index_page(
                    page_id=page_id,
                    title=title,
                    path=path,
                    workspace=workspace_config.name,
                    force_reindex=force_reindex,
                )

                if indexed_page:
                    stats.pages_indexed += 1
                    stats.indexed_pages.append(indexed_page)
                    indexed_page_ids.add(page_id)
                    self.logger.info(f"Indexed: {path}")
                else:
                    stats.pages_skipped += 1
                    indexed_page_ids.add(page_id)
                    self.logger.debug(f"Skipped (unchanged): {path}")

            except Exception as e:
                stats.pages_failed += 1
                stats.errors.append(f"{path}: {str(e)}")
                self.logger.error(f"Failed to index {path}: {e}")

        # Delete stale pages (optional cleanup)
        # This is commented out by default to preserve historical data
        # deleted = await self.delete_stale_pages(indexed_page_ids, workspace_config.name)
        # stats.pages_deleted = deleted

        self.logger.info(
            f"Indexing complete: {stats.pages_indexed} indexed, "
            f"{stats.pages_skipped} skipped, {stats.pages_failed} failed"
        )

        return stats

    async def index_page(
        self,
        page_id: str,
        title: str,
        path: str,
        workspace: str,
        force_reindex: bool = False,
    ) -> Optional[NotionPage]:
        """
        Index a single page.

        Args:
            page_id: Page ID
            title: Page title
            path: Breadcrumb path
            workspace: Workspace name
            force_reindex: If True, reindex even if unchanged

        Returns:
            NotionPage if indexed, None if skipped
        """
        # Fetch page content
        content = self.notion_client.get_page_content(page_id)
        content_hash = self._compute_content_hash(content)

        # Check if we need to reindex
        if not force_reindex and not self._should_reindex(page_id, content_hash):
            return None

        # Get page metadata for last_edited_time
        page = self.notion_client.get_page(page_id)
        last_edited_time = datetime.fromisoformat(
            page.get("last_edited_time", "").replace("Z", "+00:00")
        )

        # Generate summary using LLM
        summary = await self.generate_summary(title, path, content)

        # Create NotionPage object
        notion_page = NotionPage(
            page_id=page_id,
            title=title,
            path=path,
            summary=summary,
            last_edited_time=last_edited_time,
            content_hash=content_hash,
            workspace=workspace,
        )

        # Store in vector store
        self._store_page(notion_page)

        return notion_page

    async def generate_summary(self, title: str, path: str, content: str) -> str:
        """
        Generate LLM summary for a page.

        Args:
            title: Page title
            path: Breadcrumb path
            content: Page content

        Returns:
            Generated summary
        """
        # Truncate content if too long
        if len(content) > self.MAX_CONTENT_LENGTH:
            content = content[: self.MAX_CONTENT_LENGTH] + "..."

        prompt = self.summary_prompt.format(title=title, path=path, content=content)

        try:
            response = await self.llm.generate(
                prompt=prompt,
                system_prompt="You are a helpful assistant that creates concise summaries of documents.",
            )
            return response.text.strip() if response.text else f"Page about {title}"
        except Exception as e:
            self.logger.warning(f"Failed to generate summary for {title}: {e}")
            return f"Page about {title}"

    def _compute_content_hash(self, content: str) -> str:
        """Compute hash for content change detection."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _should_reindex(self, page_id: str, content_hash: str) -> bool:
        """
        Check if page needs reindexing.

        Args:
            page_id: Page ID
            content_hash: Current content hash

        Returns:
            True if page should be reindexed
        """
        existing = self.vector_store.get_by_id(page_id)
        if not existing:
            return True

        stored_hash = existing.get("metadata", {}).get("content_hash")
        return stored_hash != content_hash

    def _store_page(self, page: NotionPage) -> None:
        """
        Store a page in the vector store.

        Args:
            page: NotionPage to store
        """
        # Create searchable document text
        document = f"{page.title}\n{page.path}\n{page.summary}"

        # Generate embedding
        embedding = self.embedding_generator.generate_embedding(document)

        # Prepare metadata
        metadata = {
            "page_id": page.page_id,
            "title": page.title,
            "path": page.path,
            "summary": page.summary,
            "content_hash": page.content_hash,
            "last_edited_time": page.last_edited_time.isoformat(),
            "indexed_at": datetime.utcnow().isoformat(),
            "workspace": page.workspace or "",
        }

        # Delete existing entry if it exists (for updates)
        try:
            self.vector_store.delete(page.page_id)
        except Exception:
            pass  # Entry might not exist

        # Store new entry
        self.vector_store.store(
            text=document,
            embedding=embedding,
            metadata=metadata,
            id=page.page_id,
        )

    async def delete_stale_pages(
        self, current_page_ids: Set[str], workspace: str
    ) -> int:
        """
        Delete pages from index that no longer exist.

        Args:
            current_page_ids: Set of currently existing page IDs
            workspace: Workspace name to filter by

        Returns:
            Number of pages deleted
        """
        deleted_count = 0

        # This would require iterating through the entire collection
        # which is not efficient with the current VectorStore API
        # For now, we'll skip this and let stale entries remain
        # Users can use --force to rebuild the entire index

        self.logger.debug(
            "Stale page deletion not implemented - use --force to rebuild index"
        )

        return deleted_count

    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the current index."""
        # The current VectorStore doesn't have a direct count method
        # We'd need to add that functionality or query with a high limit
        return {
            "collection_name": self.vector_store.collection_name,
            "note": "Use --stats flag for detailed statistics",
        }

    async def generate_workspace_summary(
        self,
        pages: List[NotionPage],
        workspace_name: str,
    ) -> Dict[str, Any]:
        """
        Generate an overall summary of a workspace after indexing.

        Uses LLM to create a summary of what types of content are in the workspace
        based on the indexed pages.

        Args:
            pages: List of indexed NotionPage objects
            workspace_name: Name of the workspace

        Returns:
            Dictionary with workspace summary data:
            - name: Workspace name
            - page_count: Number of pages
            - topics: List of main topics extracted from paths
            - summary: LLM-generated summary of workspace content
        """
        if not pages:
            return {
                "name": workspace_name,
                "page_count": 0,
                "topics": [],
                "summary": f"Empty workspace with no indexed pages.",
            }

        # Build page list for LLM (limit to prevent token overflow)
        page_descriptions = []
        for page in pages[:50]:
            summary_preview = page.summary[:100] + "..." if len(page.summary) > 100 else page.summary
            page_descriptions.append(f"- {page.path}: {summary_preview}")

        pages_text = "\n".join(page_descriptions)

        prompt = self.WORKSPACE_SUMMARY_PROMPT.format(
            workspace_name=workspace_name,
            page_count=len(pages),
            pages=pages_text,
        )

        try:
            response = await self.llm.generate(
                prompt=prompt,
                system_prompt="You are a helpful assistant that creates concise summaries.",
            )
            summary = response.text.strip() if response.text else ""
        except Exception as e:
            self.logger.warning(f"Failed to generate workspace summary: {e}")
            summary = f"A Notion workspace containing {len(pages)} pages."

        # Extract main topics from page paths
        topics = self._extract_topics(pages)

        return {
            "name": workspace_name,
            "page_count": len(pages),
            "topics": topics,
            "summary": summary,
        }

    def _extract_topics(self, pages: List[NotionPage]) -> List[str]:
        """
        Extract main topics from page paths.

        Extracts the first-level path segments as topics.

        Args:
            pages: List of NotionPage objects

        Returns:
            List of unique topics (max 10)
        """
        topics = set()
        for page in pages:
            parts = page.path.split(" > ")
            if parts and parts[0]:
                topics.add(parts[0])
        return list(topics)[:10]

    def save_workspace_info(
        self,
        workspaces_data: List[Dict[str, Any]],
        output_path: Optional[str] = None,
    ) -> None:
        """
        Save workspace information to JSON file.

        Creates the overall summary from all workspace summaries and saves
        to data/notion/info.json for use by the prompt injection system.

        Args:
            workspaces_data: List of workspace summary dictionaries
            output_path: Path to save info.json (default: data/notion/info.json)
        """
        output_file = Path(output_path or self.DEFAULT_INFO_PATH)

        # Ensure directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Combine all workspace summaries into overall summary
        all_summaries = [
            ws.get("summary", "") for ws in workspaces_data if ws.get("summary")
        ]
        total_pages = sum(ws.get("page_count", 0) for ws in workspaces_data)

        # Build overall summary
        if workspaces_data:
            overall_summary = (
                f"Your Notion workspace contains {total_pages} indexed pages across "
                f"{len(workspaces_data)} workspace(s). "
            )
            if all_summaries:
                overall_summary += " ".join(all_summaries)
        else:
            overall_summary = "No Notion workspaces have been indexed yet."

        info = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "summary": overall_summary,
            "workspaces": workspaces_data,
        }

        with open(output_file, "w") as f:
            json.dump(info, f, indent=2)

        self.logger.info(f"Saved workspace info to {output_file}")
