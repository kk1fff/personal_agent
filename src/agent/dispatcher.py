"""Dispatcher (Concierge) agent for multi-agent orchestrator pattern."""

import logging
import time
from typing import List, Optional

from pydantic_ai import Agent, RunContext

from .base import AgentContext, AgentResult, BaseAgent
from .registry import AgentRegistry
from .specialist_prompts.dispatcher_prompt import DISPATCHER_PROMPT
from ..context.models import ConversationContext
from ..llm.base import BaseLLM
from ..tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class DispatcherAgent(BaseAgent):
    """The Dispatcher (Concierge) agent that routes requests to specialists.

    Key responsibilities:
    1. Categorize incoming requests
    2. Delegate to appropriate specialist via Agent-as-Tool
    3. Handle chitchat directly
    4. Never answer how-to questions directly
    """

    def __init__(
        self,
        llm: BaseLLM,
        agent_registry: AgentRegistry,
        agent_tools: List[BaseTool],
        timezone: str = "UTC",
    ):
        """Initialize dispatcher agent.

        Args:
            llm: LLM instance for routing decisions
            agent_registry: Registry containing all specialist agents
            agent_tools: Agent-as-Tool wrappers for specialists
            timezone: Default timezone for datetime injection
        """
        super().__init__(
            name="dispatcher",
            description="Routes requests to appropriate specialist agents",
            llm=llm,
            system_prompt=DISPATCHER_PROMPT,
            tools=agent_tools,
        )
        self.agent_registry = agent_registry
        self.timezone = timezone
        self._pydantic_agent: Optional[Agent] = None
        self._setup_agent()

    def _setup_agent(self) -> None:
        """Set up the pydantic_ai Agent with agent tools."""
        from .agent_processor import PydanticAIModelAdapter

        model = PydanticAIModelAdapter(self.llm, system_prompt=self._base_system_prompt)
        self._pydantic_agent = Agent(
            model=model,
            deps_type=ConversationContext,
        )

        # Register each agent-as-tool
        for tool in self._tools:
            self._register_tool(tool)

    def _register_tool(self, tool: BaseTool) -> None:
        """Register an agent tool with the pydantic_ai agent.

        Args:
            tool: Agent-as-Tool to register
        """
        schema = tool.get_schema()
        tool_name = schema["name"]
        tool_description = schema["description"]

        async def tool_wrapper(ctx: RunContext[ConversationContext], **kwargs) -> str:
            """Tool wrapper for PydanticAI integration."""
            context = ctx.deps
            result = await tool.execute(context, **kwargs)

            if result.success:
                return f"Result from specialist:\n{result.message or str(result.data) or 'Success'}"
            else:
                return f"Error from specialist:\n{result.error or 'Unknown error'}"

        tool_wrapper.__name__ = tool_name
        tool_wrapper.__doc__ = tool_description
        self._pydantic_agent.tool(tool_wrapper)
        logger.debug(f"[dispatcher] Registered agent tool: {tool_name}")

    def get_system_prompt(self, context: AgentContext) -> str:
        """Build dispatcher system prompt with agent descriptions.

        Args:
            context: Agent context

        Returns:
            Complete system prompt with agent registry info
        """
        from datetime import datetime
        from zoneinfo import ZoneInfo

        # Get timezone from context or use default
        timezone = context.metadata.get("timezone", self.timezone)
        try:
            tz = ZoneInfo(timezone)
            current_datetime = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            current_datetime = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            timezone = "UTC"

        # Get agent descriptions from registry
        agent_descriptions = self.agent_registry.get_agent_descriptions()

        return self._base_system_prompt.format(
            current_datetime=current_datetime,
            timezone=timezone,
            agent_descriptions=agent_descriptions,
        )

    async def process(
        self,
        message: str,
        context: AgentContext
    ) -> AgentResult:
        """Route message to appropriate specialist.

        Args:
            message: User's message
            context: Agent context

        Returns:
            AgentResult with specialist's response
        """
        start_time = time.time()
        tool_calls: List[str] = []

        try:
            # Get dynamic system prompt
            system_prompt = self.get_system_prompt(context)

            # Update model's system prompt
            self._pydantic_agent.model._system_prompt = system_prompt

            # Convert AgentContext to ConversationContext for tool compatibility
            conversation_context = ConversationContext(
                chat_id=context.chat_id,
                user_id=context.user_id,
                messages=[],
            )
            # Pass metadata through (including trace)
            conversation_context.metadata = context.metadata

            # Log dispatching
            logger.debug(f"[dispatcher] Processing: {message[:100]}...")

            # Run through pydantic_ai
            result = await self._pydantic_agent.run(
                user_prompt=message,
                deps=conversation_context,
            )

            # Extract response text
            try:
                response_text = result.data
            except AttributeError:
                response_text = result.output

            processing_time = (time.time() - start_time) * 1000

            logger.debug(
                f"[dispatcher] Completed in {processing_time:.2f}ms"
            )

            return AgentResult(
                success=True,
                response_text=response_text,
                agent_name=self.name,
                trace_id=context.trace_id,
                tool_calls_made=tool_calls,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(f"[dispatcher] Processing failed: {e}", exc_info=True)
            processing_time = (time.time() - start_time) * 1000

            return AgentResult(
                success=False,
                response_text="I'm having trouble processing your request. Please try again.",
                agent_name=self.name,
                trace_id=context.trace_id,
                tool_calls_made=tool_calls,
                processing_time_ms=processing_time,
            )
