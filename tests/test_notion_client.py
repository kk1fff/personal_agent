"""Tests for Notion client."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.notion.client import NotionClient
from src.notion.models import NotionBlock


@pytest.fixture
def mock_notion_sdk():
    """Mock notion_client.Client."""
    with patch("src.notion.client.Client") as mock:
        yield mock


@pytest.fixture
def notion_client(mock_notion_sdk):
    """Create NotionClient with mocked SDK."""
    client = NotionClient(api_key="test-api-key", rate_limit_delay=0)
    return client


class TestNotionClient:
    """Tests for NotionClient."""

    def test_init(self, mock_notion_sdk):
        """Test client initialization."""
        client = NotionClient(api_key="test-key", rate_limit_delay=0.5)
        mock_notion_sdk.assert_called_once_with(auth="test-key")
        assert client.rate_limit_delay == 0.5

    def test_get_page(self, notion_client, mock_notion_sdk):
        """Test fetching a page."""
        mock_page = {"id": "page-123", "properties": {}}
        notion_client.client.pages.retrieve.return_value = mock_page

        result = notion_client.get_page("page-123")

        notion_client.client.pages.retrieve.assert_called_once_with(page_id="page-123")
        assert result == mock_page

    def test_get_page_title_from_title_property(self, notion_client):
        """Test extracting title from page with title property."""
        page = {
            "properties": {
                "title": {
                    "type": "title",
                    "title": [{"plain_text": "My Page Title"}],
                }
            }
        }

        title = notion_client.get_page_title(page)
        assert title == "My Page Title"

    def test_get_page_title_from_name_property(self, notion_client):
        """Test extracting title from database entry with Name property."""
        page = {
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "Database Entry"}],
                }
            }
        }

        title = notion_client.get_page_title(page)
        assert title == "Database Entry"

    def test_get_page_title_untitled(self, notion_client):
        """Test fallback to Untitled when no title found."""
        page = {"properties": {}}

        title = notion_client.get_page_title(page)
        assert title == "Untitled"

    def test_get_page_title_multiple_text_parts(self, notion_client):
        """Test title with multiple text parts."""
        page = {
            "properties": {
                "title": {
                    "type": "title",
                    "title": [
                        {"plain_text": "Part 1 "},
                        {"plain_text": "Part 2"},
                    ],
                }
            }
        }

        title = notion_client.get_page_title(page)
        assert title == "Part 1 Part 2"

    def test_get_blocks_handles_pagination(self, notion_client):
        """Test that get_blocks fetches all pages of blocks."""
        # First page of results
        first_response = {
            "results": [
                {"id": "block-1", "type": "paragraph", "paragraph": {"rich_text": []}, "has_children": False}
            ],
            "has_more": True,
            "next_cursor": "cursor-1",
        }
        # Second page of results
        second_response = {
            "results": [
                {"id": "block-2", "type": "paragraph", "paragraph": {"rich_text": []}, "has_children": False}
            ],
            "has_more": False,
        }

        notion_client.client.blocks.children.list.side_effect = [first_response, second_response]

        blocks = notion_client.get_blocks("page-123")

        assert len(blocks) == 2
        assert blocks[0].block_id == "block-1"
        assert blocks[1].block_id == "block-2"
        assert notion_client.client.blocks.children.list.call_count == 2

    def test_extract_block_content_paragraph(self, notion_client):
        """Test content extraction from paragraph block."""
        block = {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"plain_text": "Hello world"}]
            },
        }

        content = notion_client._extract_block_content(block)
        assert content == "Hello world"

    def test_extract_block_content_heading(self, notion_client):
        """Test content extraction from heading block."""
        block = {
            "type": "heading_1",
            "heading_1": {
                "rich_text": [{"plain_text": "My Heading"}]
            },
        }

        content = notion_client._extract_block_content(block)
        assert content == "My Heading"

    def test_extract_block_content_code(self, notion_client):
        """Test content extraction from code block."""
        block = {
            "type": "code",
            "code": {
                "rich_text": [{"plain_text": "print('hello')"}],
                "language": "python",
            },
        }

        content = notion_client._extract_block_content(block)
        assert "python" in content
        assert "print('hello')" in content

    def test_extract_block_content_child_page(self, notion_client):
        """Test content extraction from child page block."""
        block = {
            "type": "child_page",
            "child_page": {"title": "Sub Page"},
        }

        content = notion_client._extract_block_content(block)
        assert "[Page: Sub Page]" == content

    def test_get_child_pages(self, notion_client):
        """Test getting child page IDs."""
        response = {
            "results": [
                {"id": "child-1", "type": "child_page", "child_page": {"title": "Child 1"}, "has_children": False},
                {"id": "para-1", "type": "paragraph", "paragraph": {"rich_text": []}, "has_children": False},
                {"id": "child-2", "type": "child_page", "child_page": {"title": "Child 2"}, "has_children": False},
            ],
            "has_more": False,
        }

        notion_client.client.blocks.children.list.return_value = response

        child_ids = notion_client.get_child_pages("parent-page")

        assert len(child_ids) == 2
        assert "child-1" in child_ids
        assert "child-2" in child_ids

    def test_query_database(self, notion_client):
        """Test querying database with pagination."""
        first_response = {
            "results": [{"id": "page-1"}],
            "has_more": True,
            "next_cursor": "cursor-1",
        }
        second_response = {
            "results": [{"id": "page-2"}],
            "has_more": False,
        }

        notion_client.client.databases.query.side_effect = [first_response, second_response]

        pages = list(notion_client.query_database("db-123"))

        assert len(pages) == 2
        assert pages[0]["id"] == "page-1"
        assert pages[1]["id"] == "page-2"

    def test_get_database_title(self, notion_client):
        """Test extracting database title."""
        database = {
            "title": [{"plain_text": "My Database"}]
        }

        title = notion_client.get_database_title(database)
        assert title == "My Database"

    def test_get_database_title_untitled(self, notion_client):
        """Test fallback for database without title."""
        database = {"title": []}

        title = notion_client.get_database_title(database)
        assert title == "Untitled Database"

    def test_is_database_true(self, notion_client):
        """Test is_database returns True for databases."""
        notion_client.client.databases.retrieve.return_value = {"id": "db-123"}

        assert notion_client.is_database("db-123") is True

    def test_is_database_false(self, notion_client):
        """Test is_database returns False for non-databases."""
        notion_client.client.databases.retrieve.side_effect = Exception("Not a database")

        assert notion_client.is_database("page-123") is False
