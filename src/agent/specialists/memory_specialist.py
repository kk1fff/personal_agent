"""Memory Specialist agent."""

import logging
from typing import Optional

from ..base import AgentContext
from ..specialist_prompts.memory_prompt import MEMORY_SPECIALIST_PROMPT
from .base_specialist import BaseSpecialistAgent
from ...llm.base import BaseLLM
from ...tools.base import BaseTool

logger = logging.getLogger(__name__)


class MemorySpecialist(BaseSpecialistAgent):
    """Specialist agent for conversation history retrieval.

    Handles recalling past conversations and providing context
    from previous interactions. Has access to ContextManagerTool internally.
    """

    def __init__(
        self,
        llm: BaseLLM,
        context_manager_tool: BaseTool,
    ):
        """Initialize Memory specialist.

        Args:
            llm: LLM instance for processing
            context_manager_tool: Tool for retrieving conversation history
        """
        super().__init__(
            name="memory_specialist",
            description=(
                "Recalls past conversations and provides context from previous interactions. "
                "Use this when the user asks about what they said before or past discussions."
            ),
            llm=llm,
            system_prompt=MEMORY_SPECIALIST_PROMPT,
            tools=[context_manager_tool],
            data_sources={},
        )

    def get_system_prompt(self, context: AgentContext) -> str:
        """Get system prompt with datetime context injected.

        Args:
            context: Agent context

        Returns:
            Complete system prompt with current datetime
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

        return self._base_system_prompt.format(
            current_datetime=current_datetime,
            timezone=timezone,
        )
