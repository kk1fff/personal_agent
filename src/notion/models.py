"""Pydantic models and dataclasses for Notion data."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class NotionPage:
    """Represents an indexed Notion page."""

    page_id: str
    title: str
    path: str  # Breadcrumb path: "General > Tax > 2025"
    summary: str  # LLM-generated summary
    last_edited_time: datetime
    content_hash: str  # For change detection
    parent_id: Optional[str] = None
    workspace: Optional[str] = None


@dataclass
class NotionBlock:
    """Represents a Notion block of content."""

    block_id: str
    block_type: str
    content: str
    has_children: bool = False


@dataclass
class TraversalProgress:
    """Progress tracking for workspace traversal."""

    total_pages_found: int = 0
    pages_processed: int = 0
    pages_skipped: int = 0
    current_page_title: str = ""
    current_depth: int = 0


@dataclass
class IndexingStats:
    """Statistics from an indexing run."""

    pages_indexed: int = 0
    pages_skipped: int = 0
    pages_failed: int = 0
    pages_deleted: int = 0
    errors: List[str] = field(default_factory=list)
    indexed_pages: List["NotionPage"] = field(default_factory=list)
