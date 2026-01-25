"""Calendar Specialist agent."""

import logging
from typing import List, Optional

from ..base import AgentContext
from ..specialist_prompts.calendar_prompt import CALENDAR_SPECIALIST_PROMPT
from .base_specialist import BaseSpecialistAgent
from ...llm.base import BaseLLM
from ...tools.base import BaseTool

logger = logging.getLogger(__name__)


class CalendarSpecialist(BaseSpecialistAgent):
    """Specialist agent for Google Calendar operations.

    Handles reading events and creating new calendar entries.
    Has access to CalendarReaderTool and CalendarWriterTool internally.
    """

    def __init__(
        self,
        llm: BaseLLM,
        calendar_reader_tool: Optional[BaseTool] = None,
        calendar_writer_tool: Optional[BaseTool] = None,
    ):
        """Initialize Calendar specialist.

        Args:
            llm: LLM instance for processing
            calendar_reader_tool: Tool for reading calendar events
            calendar_writer_tool: Tool for creating calendar events
        """
        tools: List[BaseTool] = []
        if calendar_reader_tool:
            tools.append(calendar_reader_tool)
        if calendar_writer_tool:
            tools.append(calendar_writer_tool)

        super().__init__(
            name="calendar_specialist",
            description=(
                "Manages Google Calendar - reads events and creates new ones. "
                "Use this for scheduling, viewing calendar, and time management."
            ),
            llm=llm,
            system_prompt=CALENDAR_SPECIALIST_PROMPT,
            tools=tools,
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
