"""Notion Specialist agent."""

import json
import logging
import time
from typing import Any, Dict, List, Optional

from ..base import AgentContext, AgentResult
from ..specialist_prompts.notion_prompt import NOTION_SPECIALIST_PROMPT
from .base_specialist import BaseSpecialistAgent
from .notion_intelligence import NotionIntelligenceEngine
from .notion_models import NotionIntelligenceConfig, SearchScope
from ...llm.base import BaseLLM
from ...tools.base import BaseTool
from ...tools.notion_search import NotionSearchTool

logger = logging.getLogger(__name__)


class NotionSpecialist(BaseSpecialistAgent):
    """Specialist agent for Notion workspace operations.

    Handles searching and retrieving content from the user's Notion workspace.
    Has access to the NotionSearchTool internally, plus a NotionIntelligenceEngine
    for multi-step LLM-powered search, re-ranking, and answer synthesis.
    """

    def __init__(
        self,
        llm: BaseLLM,
        notion_search_tool: BaseTool,
        notion_context: str = "",
        intelligence_config: Optional[NotionIntelligenceConfig] = None,
    ):
        """Initialize Notion specialist.

        Args:
            llm: LLM instance for processing
            notion_search_tool: The NotionSearchTool instance
            notion_context: Context about the Notion workspace (from info.json)
            intelligence_config: Configuration for intelligence features
        """
        super().__init__(
            name="notion_specialist",
            description=(
                "Searches and retrieves information from the Notion workspace. "
                "Use this for finding notes, documents, and stored information."
            ),
            llm=llm,
            system_prompt=NOTION_SPECIALIST_PROMPT,
            tools=[notion_search_tool],
            data_sources={"notion_context": notion_context},
        )

        # Initialize intelligence engine if we have a NotionSearchTool
        self.intelligence_engine: Optional[NotionIntelligenceEngine] = None
        if isinstance(notion_search_tool, NotionSearchTool):
            self.intelligence_engine = NotionIntelligenceEngine(
                llm=llm,
                notion_search_tool=notion_search_tool,
                workspace_context=notion_context,
                config=intelligence_config,
            )
            logger.info(
                f"[{self.name}] Intelligence engine initialized "
                f"(enabled={intelligence_config.enabled if intelligence_config else True})"
            )

    async def process(
        self,
        message: str,
        context: AgentContext
    ) -> AgentResult:
        """Process a message using intelligence engine or base processing.

        If the message is a structured NotionQuery JSON, use the intelligence
        engine for multi-step processing. Otherwise, fall back to base class
        processing which uses the pydantic_ai agent.

        Args:
            message: Delegated query (may be JSON from NotionQuery model)
            context: Agent context

        Returns:
            AgentResult with response
        """
        start_time = time.time()

        # Try to parse as NotionQuery JSON
        query_params = self._parse_notion_query(message)

        if query_params and self.intelligence_engine:
            # Use intelligence engine for structured queries
            return await self._process_with_intelligence(
                query_params, context, start_time
            )
        else:
            # Fall back to base class processing
            return await super().process(message, context)

    def _parse_notion_query(self, message: str) -> Optional[Dict[str, Any]]:
        """Try to parse message as NotionQuery JSON.

        Args:
            message: Raw message string

        Returns:
            Parsed query parameters or None if not valid JSON/NotionQuery
        """
        try:
            data = json.loads(message)
            # Check if it looks like a NotionQuery (has user_question or search_term)
            if isinstance(data, dict) and (
                "user_question" in data or "search_term" in data
            ):
                return data
        except (json.JSONDecodeError, TypeError):
            pass
        return None

    async def _process_with_intelligence(
        self,
        query_params: Dict[str, Any],
        context: AgentContext,
        start_time: float,
    ) -> AgentResult:
        """Process query using intelligence engine.

        Args:
            query_params: Parsed NotionQuery parameters
            context: Agent context
            start_time: Processing start time

        Returns:
            AgentResult with synthesized response
        """
        try:
            # Handle backward compatibility: search_term -> user_question
            user_question = query_params.get("user_question") or query_params.get(
                "search_term", ""
            )
            if not user_question:
                return AgentResult(
                    success=False,
                    response_text="No search query provided. Please specify what you're looking for.",
                    agent_name=self.name,
                    trace_id=context.trace_id,
                    processing_time_ms=(time.time() - start_time) * 1000,
                )

            # Extract other parameters
            context_hint = query_params.get("context_hint")
            time_context = query_params.get("time_context") or query_params.get(
                "date_range"
            )
            max_pages = query_params.get("max_pages_to_analyze", 5)

            # Parse search scope
            scope_str = query_params.get("search_scope", "precise")
            try:
                search_scope = SearchScope(scope_str)
            except ValueError:
                search_scope = SearchScope.PRECISE

            # Add time context to the hint if provided
            if time_context and not context_hint:
                context_hint = f"Time filter: {time_context}"
            elif time_context and context_hint:
                context_hint = f"{context_hint}. Time filter: {time_context}"

            # Set trace on intelligence engine if available
            if context.metadata.get("trace"):
                self.intelligence_engine.set_trace(context.metadata.get("trace"))

            # Process with intelligence engine
            result = await self.intelligence_engine.process_query(
                user_question=user_question,
                context_hint=context_hint,
                search_scope=search_scope,
                max_pages_to_analyze=max_pages,
            )

            processing_time = (time.time() - start_time) * 1000

            logger.debug(
                f"[{self.name}] Intelligence processing completed in {processing_time:.2f}ms "
                f"(confidence={result.confidence:.2f}, pages={result.pages_analyzed})"
            )

            return AgentResult(
                success=True,
                response_text=result.answer,
                structured_data={
                    "confidence": result.confidence,
                    "citations": [c.model_dump() for c in result.citations],
                    "gaps_identified": result.gaps_identified,
                    "follow_up_suggestions": result.follow_up_suggestions,
                    "pages_analyzed": result.pages_analyzed,
                },
                agent_name=self.name,
                trace_id=context.trace_id,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(
                f"[{self.name}] Intelligence processing failed: {e}", exc_info=True
            )
            processing_time = (time.time() - start_time) * 1000

            # Fall back to base class processing
            logger.info(f"[{self.name}] Falling back to base processing")
            return await super().process(
                query_params.get("user_question", query_params.get("search_term", "")),
                context,
            )

    def get_system_prompt(self, context: AgentContext) -> str:
        """Get system prompt with Notion context injected.

        Args:
            context: Agent context

        Returns:
            Complete system prompt with Notion workspace info
        """
        from datetime import datetime
        from zoneinfo import ZoneInfo

        # Get timezone from metadata or default to UTC
        timezone = context.metadata.get("timezone", "UTC")
        try:
            tz = ZoneInfo(timezone)
            current_datetime = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            current_datetime = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            timezone = "UTC"

        # Get Notion context from data sources
        notion_context = self.data_sources.get("notion_context", "")
        if not notion_context:
            notion_context = "No workspace summary available. Use the search tool to explore."

        return self._base_system_prompt.format(
            current_datetime=current_datetime,
            timezone=timezone,
            notion_context=notion_context,
        )
