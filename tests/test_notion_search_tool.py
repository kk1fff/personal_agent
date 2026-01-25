"""Tests for NotionSearchTool."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.tools.notion_search import NotionSearchTool
from src.context.models import ConversationContext, Message


@pytest.fixture
def mock_vector_store():
    """Create mock vector store."""
    store = Mock()
    store.search.return_value = [
        {
            "id": "page-1",
            "text": "Page 1\nRoot > Page 1\nSummary of page 1",
            "metadata": {
                "page_id": "page-1",
                "title": "Page 1",
                "path": "Root > Page 1",
                "summary": "Summary of page 1",
            },
            "distance": 0.1,
        },
        {
            "id": "page-2",
            "text": "Page 2\nRoot > Page 2\nSummary of page 2",
            "metadata": {
                "page_id": "page-2",
                "title": "Page 2",
                "path": "Root > Page 2",
                "summary": "Summary of page 2",
            },
            "distance": 0.2,
        },
    ]
    store.get_by_id.return_value = {
        "id": "page-1",
        "metadata": {
            "page_id": "page-1",
            "title": "Page 1",
            "path": "Root > Page 1",
            "summary": "Summary of page 1",
        },
    }
    return store


@pytest.fixture
def mock_embedding_generator():
    """Create mock embedding generator."""
    generator = Mock()
    generator.generate_embedding.return_value = [0.1] * 384
    return generator


@pytest.fixture
def notion_search_tool(mock_vector_store, mock_embedding_generator):
    """Create NotionSearchTool with mocks."""
    with patch("src.tools.notion_search.NotionClient") as MockClient:
        mock_client = Mock()
        mock_client.get_page.return_value = {
            "id": "page-1",
            "properties": {"title": {"type": "title", "title": [{"plain_text": "Page 1"}]}},
        }
        mock_client.get_page_title.return_value = "Page 1"
        mock_client.get_page_content.return_value = "Full content of the page"
        MockClient.return_value = mock_client

        tool = NotionSearchTool(
            api_key="test-api-key",
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_generator,
            default_results=5,
        )
        tool.notion_client = mock_client
        return tool


@pytest.fixture
def conversation_context():
    """Create a conversation context for testing."""
    return ConversationContext(
        chat_id=123,
        user_id=456,
        messages=[
            Message(
                chat_id=123,
                user_id=456,
                message_text="Hello",
                role="user",
                timestamp=datetime.now(),
            )
        ],
    )


class TestNotionSearchTool:
    """Tests for NotionSearchTool."""

    def test_init(self, mock_vector_store, mock_embedding_generator):
        """Test tool initialization."""
        with patch("src.tools.notion_search.NotionClient"):
            tool = NotionSearchTool(
                api_key="test-key",
                vector_store=mock_vector_store,
                embedding_generator=mock_embedding_generator,
            )

            assert tool.name == "notion_search"
            assert tool.default_results == 5

    @pytest.mark.asyncio
    async def test_search_returns_results(
        self, notion_search_tool, conversation_context, mock_vector_store, mock_embedding_generator
    ):
        """Test basic search returns matching pages."""
        result = await notion_search_tool.execute(
            conversation_context,
            query="test query",
            read_page=False,  # Don't fetch full page content
        )

        assert result.success is True
        assert result.data["count"] == 2
        assert len(result.data["results"]) == 2

        # Verify embedding was generated for query
        mock_embedding_generator.generate_embedding.assert_called_once_with("test query")

        # Verify vector store was searched
        mock_vector_store.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_with_no_results(
        self, notion_search_tool, conversation_context, mock_vector_store
    ):
        """Test search with no results."""
        mock_vector_store.search.return_value = []

        result = await notion_search_tool.execute(
            conversation_context,
            query="nonexistent query",
        )

        assert result.success is True
        assert result.data["count"] == 0
        assert "No matching pages" in result.message

    @pytest.mark.asyncio
    async def test_search_with_read_page(
        self, notion_search_tool, conversation_context
    ):
        """Test search with read_page=True fetches content."""
        result = await notion_search_tool.execute(
            conversation_context,
            query="test query",
            read_page=True,
        )

        assert result.success is True
        assert "page" in result.data
        assert result.data["page"]["content"] == "Full content of the page"

    @pytest.mark.asyncio
    async def test_search_with_page_id_direct(
        self, notion_search_tool, conversation_context, mock_vector_store
    ):
        """Test that providing page_id directly reads without searching."""
        result = await notion_search_tool.execute(
            conversation_context,
            page_id="page-1",
        )

        assert result.success is True
        assert result.data["page_id"] == "page-1"
        assert result.data["content"] == "Full content of the page"

        # Search should not be called when page_id is provided
        mock_vector_store.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_with_max_results(
        self, notion_search_tool, conversation_context, mock_vector_store
    ):
        """Test search respects max_results parameter."""
        await notion_search_tool.execute(
            conversation_context,
            query="test query",
            max_results=3,
        )

        call_args = mock_vector_store.search.call_args
        assert call_args.kwargs["n_results"] == 3

    @pytest.mark.asyncio
    async def test_search_requires_query_or_page_id(
        self, notion_search_tool, conversation_context
    ):
        """Test that either query or page_id is required."""
        result = await notion_search_tool.execute(
            conversation_context,
        )

        assert result.success is False
        assert "query" in result.error.lower() or "page_id" in result.error.lower()

    @pytest.mark.asyncio
    async def test_search_handles_fetch_error(
        self, notion_search_tool, conversation_context
    ):
        """Test handling of page fetch errors."""
        notion_search_tool.notion_client.get_page.side_effect = Exception("API error")

        result = await notion_search_tool.execute(
            conversation_context,
            page_id="page-1",
        )

        assert result.success is False
        assert "Failed to fetch" in result.error

    def test_get_schema(self, notion_search_tool):
        """Test schema includes all required fields."""
        schema = notion_search_tool.get_schema()

        assert schema["name"] == "notion_search"
        assert "parameters" in schema
        assert "properties" in schema["parameters"]

        props = schema["parameters"]["properties"]
        assert "query" in props
        assert "read_page" in props
        assert "page_id" in props
        assert "max_results" in props

    def test_format_search_results(self, notion_search_tool, mock_vector_store):
        """Test formatting of search results."""
        results = mock_vector_store.search.return_value
        formatted = notion_search_tool._format_search_results(results)

        assert "Found 2 matching page(s)" in formatted
        assert "Page 1" in formatted
        assert "Root > Page 1" in formatted
        assert "Summary of page 1" in formatted

    def test_format_page_content(self, notion_search_tool):
        """Test formatting of page content."""
        page_data = {
            "title": "Test Page",
            "path": "Root > Test Page",
            "summary": "This is a summary",
            "content": "Full page content here",
        }

        formatted = notion_search_tool._format_page_content(page_data)

        assert "# Test Page" in formatted
        assert "Root > Test Page" in formatted
        assert "This is a summary" in formatted
        assert "Full page content here" in formatted
