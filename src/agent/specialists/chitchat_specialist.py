"""Chitchat Specialist agent."""

import logging
import time
from typing import Optional

from ..base import AgentContext, AgentResult, BaseAgent
from ..specialist_prompts.chitchat_prompt import CHITCHAT_SPECIALIST_PROMPT
from ...llm.base import BaseLLM

logger = logging.getLogger(__name__)


class ChitchatSpecialist(BaseAgent):
    """Specialist agent for casual conversation.

    Handles greetings, thanks, and simple social exchanges.
    Has no tools - just responds directly via LLM.
    """

    def __init__(self, llm: BaseLLM):
        """Initialize Chitchat specialist.

        Args:
            llm: LLM instance for processing
        """
        super().__init__(
            name="chitchat_specialist",
            description=(
                "Handles greetings, thanks, and casual conversation. "
                "Use this for simple social exchanges that don't require tools."
            ),
            llm=llm,
            system_prompt=CHITCHAT_SPECIALIST_PROMPT,
            tools=[],  # No tools needed
        )

    async def process(
        self,
        message: str,
        context: AgentContext
    ) -> AgentResult:
        """Process a chitchat message.

        Args:
            message: User's message
            context: Agent context

        Returns:
            AgentResult with friendly response
        """
        start_time = time.time()

        try:
            system_prompt = self.get_system_prompt(context)

            # Simple LLM call without tools
            response = await self.llm.generate(
                prompt=message,
                system_prompt=system_prompt,
                tools=None,
            )

            processing_time = (time.time() - start_time) * 1000

            return AgentResult(
                success=True,
                response_text=response.text or "Hello! How can I help you?",
                agent_name=self.name,
                trace_id=context.trace_id,
                tool_calls_made=[],
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(f"[{self.name}] Processing failed: {e}", exc_info=True)
            processing_time = (time.time() - start_time) * 1000

            return AgentResult(
                success=True,  # Still return success with fallback
                response_text="Hello! How can I help you today?",
                agent_name=self.name,
                trace_id=context.trace_id,
                tool_calls_made=[],
                processing_time_ms=processing_time,
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
