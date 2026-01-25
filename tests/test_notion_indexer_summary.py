"""Tests for Notion indexer workspace summary generation."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.notion.indexer import NotionIndexer
from src.notion.models import NotionPage


@pytest.fixture
def mock_llm():
    """Create a mock LLM that returns a fixed summary."""
    llm = AsyncMock()
    llm.generate.return_value = MagicMock(
        text="This workspace contains project documentation, meeting notes, and personal ideas."
    )
    return llm


@pytest.fixture
def mock_notion_client():
    """Create a mock Notion client."""
    return MagicMock()


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    store = MagicMock()
    store.get_by_id.return_value = None
    return store


@pytest.fixture
def mock_embedding_generator():
    """Create a mock embedding generator."""
    generator = MagicMock()
    generator.generate_embedding.return_value = [0.1] * 384
    return generator


@pytest.fixture
def indexer(mock_notion_client, mock_llm, mock_vector_store, mock_embedding_generator):
    """Create a NotionIndexer with mock dependencies."""
    return NotionIndexer(
        notion_client=mock_notion_client,
        llm=mock_llm,
        vector_store=mock_vector_store,
        embedding_generator=mock_embedding_generator,
    )


@pytest.fixture
def sample_pages():
    """Create sample NotionPage objects for testing."""
    return [
        NotionPage(
            page_id="1",
            title="Project A",
            path="Work > Projects > Project A",
            summary="Details about project A including timeline and goals.",
            last_edited_time=datetime.now(),
            content_hash="abc123",
            workspace="Main",
        ),
        NotionPage(
            page_id="2",
            title="Meeting Notes",
            path="Work > Meetings > Q1 Planning",
            summary="Meeting notes from Q1 planning session.",
            last_edited_time=datetime.now(),
            content_hash="def456",
            workspace="Main",
        ),
        NotionPage(
            page_id="3",
            title="Personal Ideas",
            path="Personal > Ideas",
            summary="Collection of personal ideas and thoughts.",
            last_edited_time=datetime.now(),
            content_hash="ghi789",
            workspace="Main",
        ),
    ]


class TestGenerateWorkspaceSummary:
    """Tests for NotionIndexer.generate_workspace_summary()."""

    @pytest.mark.asyncio
    async def test_generates_summary_with_llm(self, indexer, sample_pages, mock_llm):
        """Test that workspace summary is generated using LLM."""
        result = await indexer.generate_workspace_summary(
            pages=sample_pages,
            workspace_name="Main",
        )

        assert result["name"] == "Main"
        assert result["page_count"] == 3
        assert "project documentation" in result["summary"].lower()
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_extracts_topics_from_paths(self, indexer, sample_pages):
        """Test that topics are extracted from page paths."""
        result = await indexer.generate_workspace_summary(
            pages=sample_pages,
            workspace_name="Main",
        )

        assert "Work" in result["topics"]
        assert "Personal" in result["topics"]

    @pytest.mark.asyncio
    async def test_empty_pages_list(self, indexer):
        """Test handling of empty pages list."""
        result = await indexer.generate_workspace_summary(
            pages=[],
            workspace_name="Empty",
        )

        assert result["name"] == "Empty"
        assert result["page_count"] == 0
        assert result["topics"] == []
        assert "empty" in result["summary"].lower()

    @pytest.mark.asyncio
    async def test_llm_failure_fallback(self, indexer, sample_pages, mock_llm):
        """Test fallback summary when LLM fails."""
        mock_llm.generate.side_effect = RuntimeError("LLM error")

        result = await indexer.generate_workspace_summary(
            pages=sample_pages,
            workspace_name="Main",
        )

        assert result["name"] == "Main"
        assert result["page_count"] == 3
        assert "3 pages" in result["summary"]

    @pytest.mark.asyncio
    async def test_limits_pages_for_llm(self, indexer, mock_llm):
        """Test that only first 50 pages are sent to LLM."""
        # Create 60 pages
        pages = [
            NotionPage(
                page_id=str(i),
                title=f"Page {i}",
                path=f"Category > Page {i}",
                summary=f"Summary for page {i}",
                last_edited_time=datetime.now(),
                content_hash=f"hash{i}",
                workspace="Main",
            )
            for i in range(60)
        ]

        await indexer.generate_workspace_summary(
            pages=pages,
            workspace_name="Main",
        )

        # Check that the prompt contains only 50 pages
        call_args = mock_llm.generate.call_args
        prompt = call_args.kwargs.get("prompt") or call_args.args[0]
        # Count occurrences of "Page " in prompt (should be 50, not 60)
        page_mentions = prompt.count("Page ")
        assert page_mentions <= 50

    @pytest.mark.asyncio
    async def test_topics_limited_to_ten(self, indexer):
        """Test that topics are limited to 10."""
        # Create pages with 15 different top-level paths
        pages = [
            NotionPage(
                page_id=str(i),
                title=f"Page {i}",
                path=f"Topic{i} > Subtopic",
                summary=f"Summary {i}",
                last_edited_time=datetime.now(),
                content_hash=f"hash{i}",
                workspace="Main",
            )
            for i in range(15)
        ]

        result = await indexer.generate_workspace_summary(
            pages=pages,
            workspace_name="Main",
        )

        assert len(result["topics"]) <= 10


class TestSaveWorkspaceInfo:
    """Tests for NotionIndexer.save_workspace_info()."""

    def test_saves_to_default_path(self, indexer):
        """Test saving to default path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "data" / "notion" / "info.json"

            workspaces_data = [
                {
                    "name": "Personal",
                    "page_count": 10,
                    "topics": ["Notes", "Ideas"],
                    "summary": "Personal workspace summary.",
                }
            ]

            indexer.save_workspace_info(workspaces_data, output_path=str(output_path))

            assert output_path.exists()
            with open(output_path) as f:
                data = json.load(f)

            assert "generated_at" in data
            assert "Personal workspace summary" in data["summary"]
            assert len(data["workspaces"]) == 1

    def test_creates_directory_if_not_exists(self, indexer):
        """Test that parent directories are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "deep" / "nested" / "info.json"

            indexer.save_workspace_info(
                [{"name": "Test", "page_count": 1, "topics": [], "summary": "Test"}],
                output_path=str(output_path),
            )

            assert output_path.exists()

    def test_combines_workspace_summaries(self, indexer):
        """Test that multiple workspace summaries are combined."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "info.json"

            workspaces_data = [
                {"name": "Personal", "page_count": 10, "topics": [], "summary": "Personal notes."},
                {"name": "Work", "page_count": 20, "topics": [], "summary": "Work documents."},
            ]

            indexer.save_workspace_info(workspaces_data, output_path=str(output_path))

            with open(output_path) as f:
                data = json.load(f)

            assert "30" in data["summary"]  # Total pages
            assert "2 workspace" in data["summary"]
            assert "Personal notes" in data["summary"]
            assert "Work documents" in data["summary"]

    def test_empty_workspaces(self, indexer):
        """Test saving with no workspaces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "info.json"

            indexer.save_workspace_info([], output_path=str(output_path))

            with open(output_path) as f:
                data = json.load(f)

            assert "No Notion workspaces" in data["summary"]
            assert data["workspaces"] == []

    def test_timestamp_format(self, indexer):
        """Test that timestamp is in ISO format with Z suffix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "info.json"

            indexer.save_workspace_info(
                [{"name": "Test", "page_count": 1, "topics": [], "summary": "Test"}],
                output_path=str(output_path),
            )

            with open(output_path) as f:
                data = json.load(f)

            assert data["generated_at"].endswith("Z")
            # Should be valid ISO format
            datetime.fromisoformat(data["generated_at"].replace("Z", "+00:00"))


class TestExtractTopics:
    """Tests for NotionIndexer._extract_topics()."""

    def test_extracts_first_level_paths(self, indexer, sample_pages):
        """Test extracting first-level path segments."""
        topics = indexer._extract_topics(sample_pages)

        assert "Work" in topics
        assert "Personal" in topics

    def test_deduplicates_topics(self, indexer):
        """Test that duplicate topics are removed."""
        pages = [
            NotionPage(
                page_id=str(i),
                title=f"Page {i}",
                path=f"Work > Project {i}",
                summary=f"Summary {i}",
                last_edited_time=datetime.now(),
                content_hash=f"hash{i}",
                workspace="Main",
            )
            for i in range(5)
        ]

        topics = indexer._extract_topics(pages)

        assert topics == ["Work"]

    def test_handles_empty_path(self, indexer):
        """Test handling of pages with empty paths."""
        pages = [
            NotionPage(
                page_id="1",
                title="Orphan Page",
                path="",
                summary="No path",
                last_edited_time=datetime.now(),
                content_hash="hash",
                workspace="Main",
            )
        ]

        topics = indexer._extract_topics(pages)

        assert topics == []
