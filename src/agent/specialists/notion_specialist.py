"""Notion Specialist agent."""

import logging
from typing import Any, Dict, List, Optional

from ..base import AgentContext
from ..specialist_prompts.notion_prompt import NOTION_SPECIALIST_PROMPT
from .base_specialist import BaseSpecialistAgent
from ...llm.base import BaseLLM
from ...tools.base import BaseTool

logger = logging.getLogger(__name__)


class NotionSpecialist(BaseSpecialistAgent):
    """Specialist agent for Notion workspace operations.

    Handles searching and retrieving content from the user's Notion workspace.
    Has access to the NotionSearchTool internally.
    """

    def __init__(
        self,
        llm: BaseLLM,
        notion_search_tool: BaseTool,
        notion_context: str = "",
    ):
        """Initialize Notion specialist.

        Args:
            llm: LLM instance for processing
            notion_search_tool: The NotionSearchTool instance
            notion_context: Context about the Notion workspace (from info.json)
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
