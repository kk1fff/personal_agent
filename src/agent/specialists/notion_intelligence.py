"""NotionIntelligenceEngine - Multi-step LLM processing for intelligent Notion search."""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from ...llm.base import BaseLLM
from ...tools.notion_search import NotionSearchTool
from .notion_models import (
    Citation,
    NotionIntelligenceConfig,
    RankedResult,
    RawSearchResult,
    SearchScope,
    SearchStrategy,
    SynthesizedAnswer,
)
from .notion_prompts_internal import (
    INTENT_ANALYSIS_PROMPT,
    RERANK_PROMPT,
    SYNTHESIS_NO_RESULTS_PROMPT,
    SYNTHESIS_PROMPT,
)

logger = logging.getLogger(__name__)


class NotionIntelligenceEngine:
    """Orchestrates multi-step LLM processing for intelligent Notion search.

    Pipeline:
    1. Intent Analysis - LLM generates search strategy from user question
    2. Execute Searches - Run queries against vector store
    3. Re-rank Results - LLM scores results by relevance
    4. Fetch Content - Get full page content for top results
    5. Synthesize Answer - LLM generates answer with citations
    """

    def __init__(
        self,
        llm: BaseLLM,
        notion_search_tool: NotionSearchTool,
        workspace_context: str,
        config: Optional[NotionIntelligenceConfig] = None,
    ):
        """Initialize NotionIntelligenceEngine.

        Args:
            llm: LLM instance for processing
            notion_search_tool: NotionSearchTool with vector store access
            workspace_context: Context about the Notion workspace (from info.json)
            config: Configuration for intelligence features
        """
        self.llm = llm
        self.search_tool = notion_search_tool
        self.workspace_context = workspace_context or "No workspace summary available."
        self.config = config or NotionIntelligenceConfig()

    async def process_query(
        self,
        user_question: str,
        context_hint: Optional[str] = None,
        search_scope: SearchScope = SearchScope.PRECISE,
        max_pages_to_analyze: int = 5,
    ) -> SynthesizedAnswer:
        """Main entry point for intelligent query processing.

        Args:
            user_question: The user's full question or request
            context_hint: Additional context about what they need
            search_scope: How broad the search should be
            max_pages_to_analyze: Maximum pages to fetch and analyze

        Returns:
            SynthesizedAnswer with answer, confidence, and citations
        """
        if not self.config.enabled:
            return await self._simple_search_fallback(user_question, max_pages_to_analyze)

        try:
            # Step 1: Analyze intent and generate search strategy
            if self.config.query_expansion:
                strategy = await self._analyze_intent(
                    user_question, context_hint, search_scope
                )
                logger.debug(f"Search strategy: {strategy.primary_queries}")
            else:
                # Use user question directly as the only query
                strategy = SearchStrategy(
                    primary_queries=[user_question],
                    expected_content_type="general content",
                    reasoning="Direct search using user question",
                )

            # Step 2: Execute searches
            raw_results = await self._execute_searches(
                strategy, self.config.rerank_top_n
            )

            if not raw_results:
                return await self._handle_no_results(user_question, strategy)

            # Step 3: Re-rank results with LLM
            if self.config.llm_reranking and len(raw_results) > 1:
                ranked_results = await self._rerank_results(user_question, raw_results)
            else:
                # Convert raw results to ranked with vector score as relevance
                ranked_results = [
                    RankedResult(
                        page_id=r.page_id,
                        title=r.title,
                        path=r.path,
                        summary=r.summary,
                        vector_score=r.vector_score,
                        relevance_score=r.vector_score,
                        relevance_reasoning="Ranked by vector similarity",
                    )
                    for r in raw_results
                ]

            # Sort by relevance score
            ranked_results.sort(key=lambda x: x.relevance_score, reverse=True)

            # Step 4: Fetch content for top results
            pages_to_fetch = min(self.config.fetch_top_n, max_pages_to_analyze)
            enriched_results = await self._fetch_relevant_content(
                ranked_results[:pages_to_fetch]
            )

            # Step 5: Synthesize answer
            if self.config.answer_synthesis:
                answer = await self._synthesize_answer(user_question, enriched_results)
            else:
                # Return raw content without synthesis
                answer = self._format_raw_results(enriched_results)

            return answer

        except Exception as e:
            logger.error(f"Intelligence engine error: {e}", exc_info=True)
            # Fall back to simple search
            return await self._simple_search_fallback(user_question, max_pages_to_analyze)

    async def _analyze_intent(
        self,
        user_question: str,
        context_hint: Optional[str],
        search_scope: SearchScope,
    ) -> SearchStrategy:
        """Use LLM to understand intent and generate search strategy.

        Args:
            user_question: The user's question
            context_hint: Additional context
            search_scope: How broad to search

        Returns:
            SearchStrategy with queries to execute
        """
        prompt = INTENT_ANALYSIS_PROMPT.format(
            workspace_context=self.workspace_context,
            user_question=user_question,
            context_hint=context_hint or "None provided",
            search_scope=search_scope.value,
        )

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt="You are a search strategy expert. Output only valid JSON.",
        )

        try:
            json_data = self._extract_json(response.text)
            return SearchStrategy(**json_data)
        except Exception as e:
            logger.warning(f"Failed to parse search strategy: {e}")
            # Fallback to using the question directly
            return SearchStrategy(
                primary_queries=[user_question],
                expected_content_type="general content",
                reasoning="Fallback: using question as search query",
            )

    async def _execute_searches(
        self, strategy: SearchStrategy, max_results_per_query: int
    ) -> List[RawSearchResult]:
        """Execute multiple searches and deduplicate results.

        Args:
            strategy: Search strategy with queries
            max_results_per_query: Max results per query

        Returns:
            Deduplicated list of raw search results
        """
        all_results: List[RawSearchResult] = []
        seen_ids: set = set()

        # Execute primary queries
        for query in strategy.primary_queries[: self.config.max_queries]:
            try:
                results = await self.search_tool._search_index(
                    query, max_results_per_query
                )
                for r in results:
                    metadata = r.get("metadata", {})
                    page_id = metadata.get("page_id", "")
                    if page_id and page_id not in seen_ids:
                        all_results.append(
                            RawSearchResult(
                                page_id=page_id,
                                title=metadata.get("title", "Untitled"),
                                path=metadata.get("path", ""),
                                summary=metadata.get("summary", ""),
                                vector_score=r.get("distance", 0.0),
                                metadata=metadata,
                            )
                        )
                        seen_ids.add(page_id)
            except Exception as e:
                logger.warning(f"Search query '{query}' failed: {e}")

        # Execute fallback queries if we have few results
        if len(all_results) < 3 and strategy.fallback_queries:
            for query in strategy.fallback_queries[:2]:
                try:
                    results = await self.search_tool._search_index(
                        query, max_results_per_query
                    )
                    for r in results:
                        metadata = r.get("metadata", {})
                        page_id = metadata.get("page_id", "")
                        if page_id and page_id not in seen_ids:
                            all_results.append(
                                RawSearchResult(
                                    page_id=page_id,
                                    title=metadata.get("title", "Untitled"),
                                    path=metadata.get("path", ""),
                                    summary=metadata.get("summary", ""),
                                    vector_score=r.get("distance", 0.0),
                                    metadata=metadata,
                                )
                            )
                            seen_ids.add(page_id)
                except Exception as e:
                    logger.warning(f"Fallback query '{query}' failed: {e}")

        return all_results

    async def _rerank_results(
        self, user_question: str, raw_results: List[RawSearchResult]
    ) -> List[RankedResult]:
        """Use LLM to re-rank results by actual relevance.

        Args:
            user_question: The user's question
            raw_results: Raw search results

        Returns:
            Results with LLM-assigned relevance scores
        """
        # Format results for LLM
        results_for_llm = [
            {
                "page_id": r.page_id,
                "title": r.title,
                "path": r.path,
                "summary": r.summary[:500] if r.summary else "",  # Truncate long summaries
            }
            for r in raw_results
        ]

        prompt = RERANK_PROMPT.format(
            user_question=user_question,
            results_json=json.dumps(results_for_llm, indent=2),
        )

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt="You are a relevance scoring expert. Output only valid JSON array.",
        )

        try:
            json_data = self._extract_json(response.text)
            if not isinstance(json_data, list):
                raise ValueError("Expected JSON array")

            # Build a map of page_id to ranking info
            ranking_map = {item["page_id"]: item for item in json_data}

            ranked_results = []
            for r in raw_results:
                ranking = ranking_map.get(r.page_id, {})
                ranked_results.append(
                    RankedResult(
                        page_id=r.page_id,
                        title=r.title,
                        path=r.path,
                        summary=r.summary,
                        vector_score=r.vector_score,
                        relevance_score=ranking.get("relevance_score", r.vector_score),
                        relevance_reasoning=ranking.get(
                            "relevance_reasoning", "Relevance from vector score"
                        ),
                    )
                )

            return ranked_results

        except Exception as e:
            logger.warning(f"Failed to parse reranking: {e}")
            # Return results with vector score as relevance
            return [
                RankedResult(
                    page_id=r.page_id,
                    title=r.title,
                    path=r.path,
                    summary=r.summary,
                    vector_score=r.vector_score,
                    relevance_score=r.vector_score,
                    relevance_reasoning="Fallback: using vector similarity",
                )
                for r in raw_results
            ]

    async def _fetch_relevant_content(
        self, ranked_results: List[RankedResult]
    ) -> List[RankedResult]:
        """Fetch full content for top-ranked pages.

        Args:
            ranked_results: Ranked results to fetch content for

        Returns:
            Results with content field populated
        """
        enriched = []
        for result in ranked_results:
            try:
                page_data = await self.search_tool._fetch_page_content(result.page_id)
                result.content = page_data.get("content", "")
                enriched.append(result)
            except Exception as e:
                logger.warning(f"Failed to fetch content for {result.page_id}: {e}")
                # Keep result without content
                enriched.append(result)

        return enriched

    async def _synthesize_answer(
        self, user_question: str, results: List[RankedResult]
    ) -> SynthesizedAnswer:
        """Synthesize final answer from fetched content.

        Args:
            user_question: The user's question
            results: Results with fetched content

        Returns:
            SynthesizedAnswer with answer and citations
        """
        # Format pages for LLM
        pages_content = []
        for i, r in enumerate(results, 1):
            content_preview = (r.content or r.summary)[:2000]  # Limit content length
            pages_content.append(
                f"--- Page {i}: {r.title} ---\n"
                f"Path: {r.path}\n"
                f"Page ID: {r.page_id}\n"
                f"Content:\n{content_preview}\n"
            )

        prompt = SYNTHESIS_PROMPT.format(
            user_question=user_question,
            pages_content="\n".join(pages_content),
        )

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt="You are an expert at synthesizing information from documents. Be accurate and cite sources.",
        )

        return self._parse_synthesis_response(response.text, len(results))

    async def _handle_no_results(
        self, user_question: str, strategy: SearchStrategy
    ) -> SynthesizedAnswer:
        """Handle case when no results are found.

        Args:
            user_question: The user's question
            strategy: The search strategy that was tried

        Returns:
            SynthesizedAnswer explaining no results
        """
        prompt = SYNTHESIS_NO_RESULTS_PROMPT.format(
            user_question=user_question,
            queries_tried=", ".join(strategy.primary_queries),
        )

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt="You are a helpful assistant. Be concise.",
        )

        return self._parse_synthesis_response(response.text, 0)

    async def _simple_search_fallback(
        self, user_question: str, max_results: int
    ) -> SynthesizedAnswer:
        """Simple search fallback when intelligence is disabled or fails.

        Args:
            user_question: The user's question
            max_results: Maximum results

        Returns:
            SynthesizedAnswer with basic search results
        """
        try:
            results = await self.search_tool._search_index(user_question, max_results)
            if not results:
                return SynthesizedAnswer(
                    answer=f"I couldn't find any relevant pages in your Notion workspace for: '{user_question}'",
                    confidence=0.0,
                    citations=[],
                    gaps_identified="No matching content found",
                    pages_analyzed=0,
                )

            # Get content for the best match
            best_match = results[0]
            metadata = best_match.get("metadata", {})
            page_id = metadata.get("page_id", "")

            content = ""
            if page_id:
                try:
                    page_data = await self.search_tool._fetch_page_content(page_id)
                    content = page_data.get("content", "")
                except Exception:
                    pass

            answer_parts = [f"Found relevant content in your Notion workspace:\n"]
            answer_parts.append(f"**{metadata.get('title', 'Untitled')}**")
            answer_parts.append(f"Path: {metadata.get('path', '')}")
            if metadata.get("summary"):
                answer_parts.append(f"\nSummary: {metadata.get('summary')}")
            if content:
                answer_parts.append(f"\nContent:\n{content[:1500]}...")

            if len(results) > 1:
                answer_parts.append(f"\n\nOther matches:")
                for r in results[1:4]:
                    m = r.get("metadata", {})
                    answer_parts.append(f"- {m.get('title', 'Untitled')} ({m.get('path', '')})")

            return SynthesizedAnswer(
                answer="\n".join(answer_parts),
                confidence=0.7,
                citations=[
                    Citation(
                        page_id=page_id,
                        title=metadata.get("title", "Untitled"),
                        path=metadata.get("path", ""),
                        excerpt=metadata.get("summary", "")[:200],
                    )
                ],
                pages_analyzed=1,
            )

        except Exception as e:
            logger.error(f"Simple search fallback failed: {e}")
            return SynthesizedAnswer(
                answer=f"I encountered an error while searching your Notion workspace: {str(e)}",
                confidence=0.0,
                citations=[],
                gaps_identified="Search failed",
                pages_analyzed=0,
            )

    def _format_raw_results(self, results: List[RankedResult]) -> SynthesizedAnswer:
        """Format raw results without LLM synthesis.

        Args:
            results: Ranked results with content

        Returns:
            SynthesizedAnswer with formatted content
        """
        if not results:
            return SynthesizedAnswer(
                answer="No results found.",
                confidence=0.0,
                citations=[],
                pages_analyzed=0,
            )

        answer_parts = ["Here's what I found in your Notion workspace:\n"]
        citations = []

        for i, r in enumerate(results, 1):
            answer_parts.append(f"\n### {i}. {r.title}")
            answer_parts.append(f"Path: {r.path}")
            if r.content:
                answer_parts.append(f"\n{r.content[:1000]}...")
            elif r.summary:
                answer_parts.append(f"\nSummary: {r.summary}")

            citations.append(
                Citation(
                    page_id=r.page_id,
                    title=r.title,
                    path=r.path,
                    excerpt=r.summary[:200] if r.summary else "",
                )
            )

        return SynthesizedAnswer(
            answer="\n".join(answer_parts),
            confidence=0.6,
            citations=citations,
            pages_analyzed=len(results),
        )

    def _parse_synthesis_response(
        self, response_text: str, pages_analyzed: int
    ) -> SynthesizedAnswer:
        """Parse LLM synthesis response into structured format.

        Args:
            response_text: Raw LLM response
            pages_analyzed: Number of pages that were analyzed

        Returns:
            SynthesizedAnswer
        """
        # Try to extract metadata JSON from response
        metadata = {
            "confidence": 0.7,
            "citations": [],
            "gaps_identified": None,
            "follow_up_suggestions": [],
        }

        # Split by metadata marker
        parts = response_text.split("---METADATA---")
        answer_text = parts[0].strip()

        if len(parts) > 1:
            try:
                json_data = self._extract_json(parts[1])
                if isinstance(json_data, dict):
                    metadata.update(json_data)
            except Exception as e:
                logger.debug(f"Failed to parse metadata JSON: {e}")

        # Convert citations to Citation objects
        citations = []
        for c in metadata.get("citations", []):
            if isinstance(c, dict):
                citations.append(
                    Citation(
                        page_id=c.get("page_id", ""),
                        title=c.get("title", ""),
                        path=c.get("path", ""),
                        excerpt=c.get("excerpt", ""),
                    )
                )

        return SynthesizedAnswer(
            answer=answer_text,
            confidence=metadata.get("confidence", 0.7),
            citations=citations,
            gaps_identified=metadata.get("gaps_identified"),
            follow_up_suggestions=metadata.get("follow_up_suggestions", []),
            pages_analyzed=pages_analyzed,
        )

    def _extract_json(self, text: str) -> Any:
        """Extract JSON from LLM response text.

        Handles various formats:
        - Pure JSON
        - JSON in code blocks
        - JSON with surrounding text

        Args:
            text: Raw text that may contain JSON

        Returns:
            Parsed JSON data

        Raises:
            ValueError: If no valid JSON found
        """
        if not text:
            raise ValueError("Empty text")

        text = text.strip()

        # Try parsing as pure JSON first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON in code blocks
        code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find JSON object or array
        json_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        raise ValueError(f"No valid JSON found in: {text[:200]}...")
