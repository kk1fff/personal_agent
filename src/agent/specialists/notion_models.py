"""Pydantic models for NotionSpecialist multi-step processing."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SearchScope(str, Enum):
    """How broad the search should be."""

    PRECISE = "precise"  # Single specific document expected
    EXPLORATORY = "exploratory"  # Browse/discover related content
    COMPREHENSIVE = "comprehensive"  # Gather info from multiple sources


class SearchStrategy(BaseModel):
    """LLM-generated search strategy from intent analysis."""

    primary_queries: List[str] = Field(
        description="Main search queries to execute (1-3 queries)"
    )
    fallback_queries: Optional[List[str]] = Field(
        default=None,
        description="Alternative queries if primary returns poor results",
    )
    expected_content_type: str = Field(
        description="What kind of content we expect (notes, project docs, meeting notes, etc.)"
    )
    reasoning: str = Field(description="Brief explanation of the search strategy")


class RawSearchResult(BaseModel):
    """A raw search result from vector store."""

    page_id: str
    title: str
    path: str
    summary: str
    vector_score: float  # Cosine similarity score from vector search
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RankedResult(BaseModel):
    """A search result with LLM-assigned relevance score."""

    page_id: str
    title: str
    path: str
    summary: str
    vector_score: float  # Original cosine similarity
    relevance_score: float = Field(
        ge=0.0, le=1.0, description="LLM-assigned relevance (0-1)"
    )
    relevance_reasoning: str = Field(description="Why this is/isn't relevant")
    content: Optional[str] = None  # Full content if fetched


class Citation(BaseModel):
    """A citation from a Notion page."""

    page_id: str
    title: str
    path: str
    excerpt: str = Field(description="Relevant quote or excerpt from the page")


class SynthesizedAnswer(BaseModel):
    """Final synthesized answer with citations."""

    answer: str = Field(description="The synthesized answer to the user's question")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in the answer (0-1)"
    )
    citations: List[Citation] = Field(
        default_factory=list, description="Citations from source pages"
    )
    gaps_identified: Optional[str] = Field(
        default=None, description="What information might be missing"
    )
    follow_up_suggestions: List[str] = Field(
        default_factory=list, description="Suggested follow-up questions"
    )
    pages_analyzed: int = Field(
        default=0, description="Number of pages analyzed to generate this answer"
    )


class NotionIntelligenceConfig(BaseModel):
    """Configuration for NotionIntelligenceEngine."""

    enabled: bool = Field(
        default=True, description="Master switch for intelligence features"
    )
    query_expansion: bool = Field(
        default=True, description="Enable LLM-based query expansion"
    )
    llm_reranking: bool = Field(
        default=True, description="Enable LLM-based result re-ranking"
    )
    answer_synthesis: bool = Field(
        default=True, description="Enable LLM-based answer synthesis"
    )
    max_queries: int = Field(
        default=3, ge=1, le=5, description="Max queries in expansion"
    )
    rerank_top_n: int = Field(
        default=10, ge=1, le=20, description="Results to consider for re-ranking"
    )
    fetch_top_n: int = Field(
        default=3, ge=1, le=10, description="Pages to fetch full content"
    )
