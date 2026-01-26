"""Tests for NotionIntelligenceEngine."""

import json
import pytest
from unittest.mock import Mock, AsyncMock, patch

from src.agent.specialists.notion_intelligence import NotionIntelligenceEngine
from src.agent.specialists.notion_models import (
    NotionIntelligenceConfig,
    SearchScope,
    SearchStrategy,
    RawSearchResult,
    RankedResult,
    SynthesizedAnswer,
)
from src.llm.base import LLMResponse


@pytest.fixture
def mock_llm():
    """Create mock LLM."""
    llm = Mock()
    llm.generate = AsyncMock()
    return llm


@pytest.fixture
def mock_notion_search_tool():
    """Create mock NotionSearchTool."""
    tool = Mock()
    tool._search_index = AsyncMock(return_value=[
        {
            "id": "page-1",
            "metadata": {
                "page_id": "page-1",
                "title": "Project Notes",
                "path": "Work > Projects > Notes",
                "summary": "Notes from the project meeting",
            },
            "distance": 0.15,
        },
        {
            "id": "page-2",
            "metadata": {
                "page_id": "page-2",
                "title": "Meeting Minutes",
                "path": "Work > Meetings",
                "summary": "Minutes from last week's meeting",
            },
            "distance": 0.25,
        },
    ])
    tool._fetch_page_content = AsyncMock(return_value={
        "page_id": "page-1",
        "title": "Project Notes",
        "path": "Work > Projects > Notes",
        "summary": "Notes from the project meeting",
        "content": "Full content of the project notes page including details.",
    })
    return tool


@pytest.fixture
def intelligence_engine(mock_llm, mock_notion_search_tool):
    """Create NotionIntelligenceEngine with mocks."""
    return NotionIntelligenceEngine(
        llm=mock_llm,
        notion_search_tool=mock_notion_search_tool,
        workspace_context="Test workspace with project documentation.",
        config=NotionIntelligenceConfig(enabled=True),
    )


@pytest.fixture
def disabled_engine(mock_llm, mock_notion_search_tool):
    """Create disabled NotionIntelligenceEngine."""
    return NotionIntelligenceEngine(
        llm=mock_llm,
        notion_search_tool=mock_notion_search_tool,
        workspace_context="Test workspace",
        config=NotionIntelligenceConfig(enabled=False),
    )


class TestNotionIntelligenceEngineInit:
    """Tests for engine initialization."""

    def test_init_with_defaults(self, mock_llm, mock_notion_search_tool):
        """Test initialization with default config."""
        engine = NotionIntelligenceEngine(
            llm=mock_llm,
            notion_search_tool=mock_notion_search_tool,
            workspace_context="Test context",
        )

        assert engine.llm == mock_llm
        assert engine.search_tool == mock_notion_search_tool
        assert engine.workspace_context == "Test context"
        assert engine.config.enabled is True

    def test_init_with_custom_config(self, mock_llm, mock_notion_search_tool):
        """Test initialization with custom config."""
        config = NotionIntelligenceConfig(
            enabled=True,
            query_expansion=False,
            llm_reranking=False,
            answer_synthesis=True,
            max_queries=2,
        )

        engine = NotionIntelligenceEngine(
            llm=mock_llm,
            notion_search_tool=mock_notion_search_tool,
            workspace_context="Test",
            config=config,
        )

        assert engine.config.query_expansion is False
        assert engine.config.llm_reranking is False
        assert engine.config.max_queries == 2


class TestIntentAnalysis:
    """Tests for intent analysis step."""

    @pytest.mark.asyncio
    async def test_analyze_intent_success(self, intelligence_engine, mock_llm):
        """Test successful intent analysis."""
        mock_llm.generate.return_value = LLMResponse(
            text=json.dumps({
                "primary_queries": ["project meeting notes", "project decisions"],
                "fallback_queries": ["meeting summary"],
                "expected_content_type": "meeting notes",
                "reasoning": "User wants project meeting information",
            })
        )

        strategy = await intelligence_engine._analyze_intent(
            user_question="What were the key decisions from the project meeting?",
            context_hint="Looking for recent meetings",
            search_scope=SearchScope.PRECISE,
        )

        assert len(strategy.primary_queries) == 2
        assert "project meeting notes" in strategy.primary_queries
        assert strategy.expected_content_type == "meeting notes"

    @pytest.mark.asyncio
    async def test_analyze_intent_fallback_on_invalid_json(
        self, intelligence_engine, mock_llm
    ):
        """Test fallback when LLM returns invalid JSON."""
        mock_llm.generate.return_value = LLMResponse(text="Invalid response")

        strategy = await intelligence_engine._analyze_intent(
            user_question="What is the project status?",
            context_hint=None,
            search_scope=SearchScope.PRECISE,
        )

        # Should fallback to using question directly
        assert "What is the project status?" in strategy.primary_queries
        assert "Fallback" in strategy.reasoning


class TestExecuteSearches:
    """Tests for search execution step."""

    @pytest.mark.asyncio
    async def test_execute_searches_single_query(
        self, intelligence_engine, mock_notion_search_tool
    ):
        """Test executing a single search query."""
        strategy = SearchStrategy(
            primary_queries=["project notes"],
            expected_content_type="notes",
            reasoning="test",
        )

        results = await intelligence_engine._execute_searches(strategy, max_results_per_query=5)

        assert len(results) == 2
        assert results[0].page_id == "page-1"
        assert results[0].title == "Project Notes"
        mock_notion_search_tool._search_index.assert_called_once_with("project notes", 5)

    @pytest.mark.asyncio
    async def test_execute_searches_multiple_queries_deduplicates(
        self, intelligence_engine, mock_notion_search_tool
    ):
        """Test that multiple queries deduplicate results."""
        strategy = SearchStrategy(
            primary_queries=["query1", "query2"],
            expected_content_type="notes",
            reasoning="test",
        )

        # Both queries return the same pages
        results = await intelligence_engine._execute_searches(strategy, max_results_per_query=5)

        # Should deduplicate - only 2 unique pages
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_execute_searches_uses_fallback_queries(
        self, intelligence_engine, mock_notion_search_tool
    ):
        """Test fallback queries are used when primary returns few results."""
        # Primary query returns only 1 result
        mock_notion_search_tool._search_index.side_effect = [
            [{"id": "p1", "metadata": {"page_id": "p1", "title": "T1", "path": "", "summary": ""}, "distance": 0.1}],
            [{"id": "p2", "metadata": {"page_id": "p2", "title": "T2", "path": "", "summary": ""}, "distance": 0.2}],
        ]

        strategy = SearchStrategy(
            primary_queries=["primary"],
            fallback_queries=["fallback"],
            expected_content_type="notes",
            reasoning="test",
        )

        results = await intelligence_engine._execute_searches(strategy, max_results_per_query=5)

        # Should have results from both primary and fallback
        assert len(results) == 2
        assert mock_notion_search_tool._search_index.call_count == 2


class TestReranking:
    """Tests for LLM re-ranking step."""

    @pytest.mark.asyncio
    async def test_rerank_results_success(self, intelligence_engine, mock_llm):
        """Test successful re-ranking."""
        raw_results = [
            RawSearchResult(page_id="p1", title="T1", path="P1", summary="S1", vector_score=0.5),
            RawSearchResult(page_id="p2", title="T2", path="P2", summary="S2", vector_score=0.8),
        ]

        mock_llm.generate.return_value = LLMResponse(
            text=json.dumps([
                {"page_id": "p1", "relevance_score": 0.9, "relevance_reasoning": "Highly relevant"},
                {"page_id": "p2", "relevance_score": 0.4, "relevance_reasoning": "Less relevant"},
            ])
        )

        ranked = await intelligence_engine._rerank_results("test question", raw_results)

        assert len(ranked) == 2
        # p1 should have higher relevance despite lower vector score
        p1 = next(r for r in ranked if r.page_id == "p1")
        assert p1.relevance_score == 0.9

    @pytest.mark.asyncio
    async def test_rerank_results_fallback_on_error(self, intelligence_engine, mock_llm):
        """Test fallback to vector scores on reranking error."""
        raw_results = [
            RawSearchResult(page_id="p1", title="T1", path="P1", summary="S1", vector_score=0.5),
        ]

        mock_llm.generate.return_value = LLMResponse(text="Invalid JSON")

        ranked = await intelligence_engine._rerank_results("test question", raw_results)

        assert len(ranked) == 1
        # Should use vector_score as relevance
        assert ranked[0].relevance_score == 0.5


class TestContentFetching:
    """Tests for content fetching step."""

    @pytest.mark.asyncio
    async def test_fetch_content_success(
        self, intelligence_engine, mock_notion_search_tool
    ):
        """Test successful content fetching."""
        results = [
            RankedResult(
                page_id="page-1", title="T1", path="P1", summary="S1",
                vector_score=0.5, relevance_score=0.9, relevance_reasoning="Relevant"
            ),
        ]

        enriched = await intelligence_engine._fetch_relevant_content(results)

        assert len(enriched) == 1
        assert enriched[0].content is not None
        assert "Full content" in enriched[0].content

    @pytest.mark.asyncio
    async def test_fetch_content_handles_errors(
        self, intelligence_engine, mock_notion_search_tool
    ):
        """Test that errors in fetching don't break the process."""
        mock_notion_search_tool._fetch_page_content.side_effect = Exception("API error")

        results = [
            RankedResult(
                page_id="page-1", title="T1", path="P1", summary="S1",
                vector_score=0.5, relevance_score=0.9, relevance_reasoning="Relevant"
            ),
        ]

        enriched = await intelligence_engine._fetch_relevant_content(results)

        # Should still return the result, just without content
        assert len(enriched) == 1


class TestAnswerSynthesis:
    """Tests for answer synthesis step."""

    @pytest.mark.asyncio
    async def test_synthesize_answer_success(self, intelligence_engine, mock_llm):
        """Test successful answer synthesis."""
        results = [
            RankedResult(
                page_id="p1", title="Project Notes", path="Work/Projects",
                summary="Meeting notes", vector_score=0.5, relevance_score=0.9,
                relevance_reasoning="Relevant", content="The project deadline is March 15."
            ),
        ]

        mock_llm.generate.return_value = LLMResponse(
            text="""Based on your notes, the project deadline is March 15th [Page: Project Notes].

---METADATA---
{
    "confidence": 0.95,
    "citations": [{"page_id": "p1", "title": "Project Notes", "path": "Work/Projects", "excerpt": "deadline is March 15"}],
    "gaps_identified": null,
    "follow_up_suggestions": ["Who is responsible for the deliverables?"]
}"""
        )

        answer = await intelligence_engine._synthesize_answer("When is the deadline?", results)

        assert "March 15" in answer.answer
        assert answer.confidence == 0.95
        assert len(answer.citations) == 1
        assert answer.citations[0].page_id == "p1"

    @pytest.mark.asyncio
    async def test_synthesize_answer_without_metadata(self, intelligence_engine, mock_llm):
        """Test synthesis when LLM doesn't include metadata section."""
        results = [
            RankedResult(
                page_id="p1", title="Notes", path="Work",
                summary="Notes", vector_score=0.5, relevance_score=0.9,
                relevance_reasoning="Relevant", content="Content here"
            ),
        ]

        mock_llm.generate.return_value = LLMResponse(
            text="Based on your notes, the answer is X."
        )

        answer = await intelligence_engine._synthesize_answer("Question?", results)

        assert "answer is X" in answer.answer
        # Should have default confidence
        assert answer.confidence == 0.7

    @pytest.mark.asyncio
    async def test_synthesize_answer_with_flexible_metadata(self, intelligence_engine, mock_llm):
        """Test synthesis when LLM returns non-standard metadata formats."""
        results = [
            RankedResult(
                page_id="p1", title="Notes", path="Work",
                summary="Notes", vector_score=0.5, relevance_score=0.9,
                relevance_reasoning="Relevant", content="Content here"
            ),
        ]

        # LLM returns gaps as list and suggestions as dicts
        mock_llm.generate.return_value = LLMResponse(
            text="""Here is the answer.

---METADATA---
{
    "confidence": 0.8,
    "citations": [],
    "gaps_identified": [{"detail": "Missing budget info"}, {"detail": "No timeline"}],
    "follow_up_suggestions": [
        {"question": "What is the budget?"},
        {"question": "When is the deadline?"}
    ]
}"""
        )

        answer = await intelligence_engine._synthesize_answer("Question?", results)

        assert answer.confidence == 0.8
        # gaps_identified should be converted to string
        assert "Missing budget info" in answer.gaps_identified
        assert "No timeline" in answer.gaps_identified
        # follow_up_suggestions should extract question strings
        assert "What is the budget?" in answer.follow_up_suggestions
        assert "When is the deadline?" in answer.follow_up_suggestions


class TestFullPipeline:
    """Tests for the full processing pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_success(
        self, intelligence_engine, mock_llm, mock_notion_search_tool
    ):
        """Test full pipeline from question to answer."""
        # Set up LLM responses for each step
        mock_llm.generate.side_effect = [
            # Intent analysis
            LLMResponse(text=json.dumps({
                "primary_queries": ["project deadline"],
                "expected_content_type": "project notes",
                "reasoning": "User asking about deadline",
            })),
            # Reranking
            LLMResponse(text=json.dumps([
                {"page_id": "page-1", "relevance_score": 0.9, "relevance_reasoning": "Relevant"},
                {"page_id": "page-2", "relevance_score": 0.3, "relevance_reasoning": "Less relevant"},
            ])),
            # Synthesis
            LLMResponse(text="""The deadline is March 15.

---METADATA---
{"confidence": 0.9, "citations": [], "gaps_identified": null, "follow_up_suggestions": []}"""),
        ]

        result = await intelligence_engine.process_query(
            user_question="When is the project deadline?",
            context_hint="Looking for dates",
            search_scope=SearchScope.PRECISE,
        )

        assert result.answer is not None
        assert "deadline" in result.answer.lower() or "March" in result.answer
        assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_disabled_engine_uses_fallback(
        self, disabled_engine, mock_notion_search_tool
    ):
        """Test that disabled engine uses simple fallback."""
        result = await disabled_engine.process_query(
            user_question="What are the project notes?",
        )

        # Should still return results via fallback
        assert result.answer is not None
        # Fallback should be used, not the full pipeline
        assert disabled_engine.llm.generate.call_count == 0

    @pytest.mark.asyncio
    async def test_pipeline_handles_no_results(
        self, intelligence_engine, mock_llm, mock_notion_search_tool
    ):
        """Test pipeline handles case when no results found."""
        mock_notion_search_tool._search_index.return_value = []

        mock_llm.generate.side_effect = [
            # Intent analysis
            LLMResponse(text=json.dumps({
                "primary_queries": ["nonexistent topic"],
                "expected_content_type": "notes",
                "reasoning": "test",
            })),
            # Handle no results response
            LLMResponse(text="""I couldn't find any relevant content.

---METADATA---
{"confidence": 0.0, "citations": [], "gaps_identified": "No content found", "follow_up_suggestions": []}"""),
        ]

        result = await intelligence_engine.process_query(
            user_question="What about something that doesn't exist?",
        )

        assert result.confidence == 0.0


class TestJSONExtraction:
    """Tests for JSON extraction helper."""

    def test_extract_pure_json(self, intelligence_engine):
        """Test extraction of pure JSON."""
        text = '{"key": "value"}'
        result = intelligence_engine._extract_json(text)
        assert result == {"key": "value"}

    def test_extract_json_from_code_block(self, intelligence_engine):
        """Test extraction of JSON from code block."""
        text = '''Here is the result:
```json
{"key": "value"}
```'''
        result = intelligence_engine._extract_json(text)
        assert result == {"key": "value"}

    def test_extract_json_array(self, intelligence_engine):
        """Test extraction of JSON array."""
        text = '[{"id": 1}, {"id": 2}]'
        result = intelligence_engine._extract_json(text)
        assert len(result) == 2

    def test_extract_json_with_surrounding_text(self, intelligence_engine):
        """Test extraction of JSON with surrounding text."""
        text = 'Some text before {"key": "value"} and after'
        result = intelligence_engine._extract_json(text)
        assert result == {"key": "value"}

    def test_extract_json_raises_on_invalid(self, intelligence_engine):
        """Test that invalid JSON raises ValueError."""
        with pytest.raises(ValueError):
            intelligence_engine._extract_json("not json at all")

    def test_extract_json_from_code_block_with_newlines(self, intelligence_engine):
        """Test extraction of JSON from code block with newlines."""
        text = '''Here is the result:
```json
{
    "primary_queries": [
        "query1",
        "query2"
    ],
    "reasoning": "test"
}
```'''
        result = intelligence_engine._extract_json(text)
        assert result["primary_queries"] == ["query1", "query2"]
        assert result["reasoning"] == "test"

    def test_extract_json_nested_braces(self, intelligence_engine):
        """Test extraction of JSON with nested objects."""
        text = '{"outer": {"inner": {"deep": "value"}}}'
        result = intelligence_engine._extract_json(text)
        assert result["outer"]["inner"]["deep"] == "value"

    def test_find_json_object_helper(self, intelligence_engine):
        """Test the _find_json_object helper method."""
        text = '{"key": "value with { brace } inside"} extra'
        result = intelligence_engine._find_json_object(text)
        assert result == '{"key": "value with { brace } inside"}'

    def test_find_json_array_helper(self, intelligence_engine):
        """Test the _find_json_array helper method."""
        text = '["a", "b", ["nested"]] extra'
        result = intelligence_engine._find_json_array(text)
        assert result == '["a", "b", ["nested"]]'


class TestConfigOptions:
    """Tests for configuration options."""

    @pytest.mark.asyncio
    async def test_skip_query_expansion(self, mock_llm, mock_notion_search_tool):
        """Test that query expansion can be skipped."""
        engine = NotionIntelligenceEngine(
            llm=mock_llm,
            notion_search_tool=mock_notion_search_tool,
            workspace_context="Test",
            config=NotionIntelligenceConfig(
                enabled=True,
                query_expansion=False,
                llm_reranking=True,
                answer_synthesis=True,
            ),
        )

        mock_llm.generate.side_effect = [
            # Only reranking and synthesis (no intent analysis)
            LLMResponse(text=json.dumps([
                {"page_id": "page-1", "relevance_score": 0.9, "relevance_reasoning": "R"},
                {"page_id": "page-2", "relevance_score": 0.5, "relevance_reasoning": "R"},
            ])),
            LLMResponse(text="Answer here\n\n---METADATA---\n{\"confidence\": 0.8, \"citations\": []}"),
        ]

        result = await engine.process_query(user_question="test question")

        # Should have used question directly as search query
        mock_notion_search_tool._search_index.assert_called_with("test question", 10)

    @pytest.mark.asyncio
    async def test_skip_reranking(self, mock_llm, mock_notion_search_tool):
        """Test that reranking can be skipped."""
        engine = NotionIntelligenceEngine(
            llm=mock_llm,
            notion_search_tool=mock_notion_search_tool,
            workspace_context="Test",
            config=NotionIntelligenceConfig(
                enabled=True,
                query_expansion=True,
                llm_reranking=False,
                answer_synthesis=True,
            ),
        )

        mock_llm.generate.side_effect = [
            # Intent analysis
            LLMResponse(text=json.dumps({
                "primary_queries": ["test"],
                "expected_content_type": "notes",
                "reasoning": "test",
            })),
            # Synthesis only (no reranking)
            LLMResponse(text="Answer\n\n---METADATA---\n{\"confidence\": 0.8, \"citations\": []}"),
        ]

        result = await engine.process_query(user_question="test question")

        # Only 2 LLM calls (intent + synthesis, no reranking)
        assert mock_llm.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_skip_synthesis(self, mock_llm, mock_notion_search_tool):
        """Test that synthesis can be skipped."""
        engine = NotionIntelligenceEngine(
            llm=mock_llm,
            notion_search_tool=mock_notion_search_tool,
            workspace_context="Test",
            config=NotionIntelligenceConfig(
                enabled=True,
                query_expansion=False,
                llm_reranking=False,
                answer_synthesis=False,
            ),
        )

        result = await engine.process_query(user_question="test question")

        # No LLM calls at all (all features disabled except enabled=True)
        assert mock_llm.generate.call_count == 0
        # Should return formatted raw results
        assert "Project Notes" in result.answer
