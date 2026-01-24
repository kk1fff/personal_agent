"""Tests for Notion indexer."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.notion.indexer import NotionIndexer
from src.notion.models import NotionPage, IndexingStats
from src.config.config_schema import NotionWorkspaceConfig


@pytest.fixture
def mock_notion_client():
    """Create mock Notion client."""
    client = Mock()
    client.get_page.return_value = {
        "id": "page-123",
        "last_edited_time": "2024-01-15T10:00:00.000Z",
    }
    client.get_page_title.return_value = "Test Page"
    client.get_page_content.return_value = "Page content here"
    client.get_child_pages.return_value = []
    client.is_database.return_value = False
    return client


@pytest.fixture
def mock_llm():
    """Create mock LLM."""
    llm = AsyncMock()
    llm.generate.return_value = Mock(text="This is a summary of the page.")
    return llm


@pytest.fixture
def mock_vector_store():
    """Create mock vector store."""
    store = Mock()
    store.get_by_id.return_value = None  # Page not indexed yet
    store.store.return_value = "page-123"
    store.delete.return_value = None
    store.collection_name = "notion_pages"
    return store


@pytest.fixture
def mock_embedding_generator():
    """Create mock embedding generator."""
    generator = Mock()
    generator.generate_embedding.return_value = [0.1] * 384  # Mock embedding
    return generator


@pytest.fixture
def indexer(mock_notion_client, mock_llm, mock_vector_store, mock_embedding_generator):
    """Create NotionIndexer with mocks."""
    return NotionIndexer(
        notion_client=mock_notion_client,
        llm=mock_llm,
        vector_store=mock_vector_store,
        embedding_generator=mock_embedding_generator,
    )


@pytest.fixture
def workspace_config():
    """Create workspace configuration."""
    return NotionWorkspaceConfig(
        name="test-workspace",
        root_page_ids=["root-page-1"],
        database_ids=[],
        exclude_page_ids=[],
        max_depth=5,
    )


class TestNotionIndexer:
    """Tests for NotionIndexer."""

    @pytest.mark.asyncio
    async def test_index_page_new(
        self, indexer, mock_notion_client, mock_llm, mock_vector_store, mock_embedding_generator
    ):
        """Test indexing a new page."""
        result = await indexer.index_page(
            page_id="page-123",
            title="Test Page",
            path="Root > Test Page",
            workspace="test-workspace",
        )

        assert result is not None
        assert result.page_id == "page-123"
        assert result.title == "Test Page"
        assert result.path == "Root > Test Page"
        assert result.summary == "This is a summary of the page."

        # Verify LLM was called for summary
        mock_llm.generate.assert_called_once()

        # Verify embedding was generated
        mock_embedding_generator.generate_embedding.assert_called_once()

        # Verify stored in vector store
        mock_vector_store.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_page_skips_unchanged(
        self, indexer, mock_vector_store
    ):
        """Test that unchanged pages are skipped."""
        # Simulate page already indexed with same hash
        content_hash = indexer._compute_content_hash("Page content here")
        mock_vector_store.get_by_id.return_value = {
            "metadata": {"content_hash": content_hash}
        }

        result = await indexer.index_page(
            page_id="page-123",
            title="Test Page",
            path="Root > Test Page",
            workspace="test-workspace",
            force_reindex=False,
        )

        assert result is None  # Skipped

    @pytest.mark.asyncio
    async def test_index_page_force_reindex(
        self, indexer, mock_vector_store, mock_llm
    ):
        """Test that force_reindex reindexes regardless of hash."""
        # Simulate page already indexed with same hash
        content_hash = indexer._compute_content_hash("Page content here")
        mock_vector_store.get_by_id.return_value = {
            "metadata": {"content_hash": content_hash}
        }

        result = await indexer.index_page(
            page_id="page-123",
            title="Test Page",
            path="Root > Test Page",
            workspace="test-workspace",
            force_reindex=True,
        )

        assert result is not None
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_summary(self, indexer, mock_llm):
        """Test summary generation."""
        summary = await indexer.generate_summary(
            title="Test Page",
            path="Root > Test Page",
            content="This is the content of the page.",
        )

        assert summary == "This is a summary of the page."
        mock_llm.generate.assert_called_once()

        # Check that the prompt contains the page info
        call_args = mock_llm.generate.call_args
        prompt = call_args.kwargs.get("prompt") or call_args.args[0]
        assert "Test Page" in prompt
        assert "Root > Test Page" in prompt

    @pytest.mark.asyncio
    async def test_generate_summary_truncates_long_content(self, indexer, mock_llm):
        """Test that long content is truncated."""
        long_content = "x" * 10000  # Longer than MAX_CONTENT_LENGTH

        await indexer.generate_summary(
            title="Test Page",
            path="Root > Test Page",
            content=long_content,
        )

        call_args = mock_llm.generate.call_args
        prompt = call_args.kwargs.get("prompt") or call_args.args[0]
        assert len(prompt) < len(long_content) + 1000  # Should be truncated

    @pytest.mark.asyncio
    async def test_generate_summary_fallback_on_error(self, indexer, mock_llm):
        """Test fallback summary on LLM error."""
        mock_llm.generate.side_effect = Exception("LLM error")

        summary = await indexer.generate_summary(
            title="Test Page",
            path="Root > Test Page",
            content="Content",
        )

        assert "Test Page" in summary  # Fallback should include title

    def test_compute_content_hash(self, indexer):
        """Test content hash computation."""
        hash1 = indexer._compute_content_hash("content")
        hash2 = indexer._compute_content_hash("content")
        hash3 = indexer._compute_content_hash("different content")

        assert hash1 == hash2  # Same content = same hash
        assert hash1 != hash3  # Different content = different hash
        assert len(hash1) == 16  # Should be truncated

    def test_should_reindex_new_page(self, indexer, mock_vector_store):
        """Test should_reindex for new page."""
        mock_vector_store.get_by_id.return_value = None

        assert indexer._should_reindex("page-123", "hash123") is True

    def test_should_reindex_changed_page(self, indexer, mock_vector_store):
        """Test should_reindex for changed page."""
        mock_vector_store.get_by_id.return_value = {
            "metadata": {"content_hash": "old-hash"}
        }

        assert indexer._should_reindex("page-123", "new-hash") is True

    def test_should_reindex_unchanged_page(self, indexer, mock_vector_store):
        """Test should_reindex for unchanged page."""
        mock_vector_store.get_by_id.return_value = {
            "metadata": {"content_hash": "same-hash"}
        }

        assert indexer._should_reindex("page-123", "same-hash") is False

    @pytest.mark.asyncio
    async def test_index_workspace(
        self, indexer, workspace_config, mock_notion_client
    ):
        """Test workspace indexing."""
        # Setup traversal to return one page
        with patch("src.notion.indexer.WorkspaceTraverser") as MockTraverser:
            mock_traverser = Mock()
            mock_traverser.traverse.return_value = iter([
                ("page-1", "Page 1", "Root > Page 1"),
            ])
            MockTraverser.return_value = mock_traverser

            stats = await indexer.index_workspace(workspace_config)

            assert stats.pages_indexed == 1
            assert stats.pages_skipped == 0
            assert stats.pages_failed == 0

    def test_get_index_stats(self, indexer):
        """Test getting index statistics."""
        stats = indexer.get_index_stats()

        assert "collection_name" in stats
        assert stats["collection_name"] == "notion_pages"
