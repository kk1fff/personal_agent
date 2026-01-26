"""Base class for specialist agents."""

import logging
import time
from abc import abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

from ..base import AgentContext, AgentResult, BaseAgent
from ...llm.base import BaseLLM
from ...tools.base import BaseTool, ToolResult
from ...context.models import ConversationContext

logger = logging.getLogger(__name__)


class SpecialistRequest(BaseModel):
    """Base request model for specialist agents."""
    query: str
    context_summary: Optional[str] = None
    additional_params: Dict[str, Any] = {}


class SpecialistResponse(BaseModel):
    """Base response model for specialist agents."""
    answer: str
    confidence: float = 1.0
    sources: List[str] = []
    follow_up_suggestions: List[str] = []


class BaseSpecialistAgent(BaseAgent):
    """Base class for specialist agents with structured I/O.

    Specialists are "blind" to other agents' tools - they only know
    about their own domain-specific tools. They receive context from
    the Dispatcher but their internal tool calls are hidden from it.
    """

    # Subclasses can override these for custom request/response models
    request_model: type[BaseModel] = SpecialistRequest
    response_model: type[BaseModel] = SpecialistResponse

    def __init__(
        self,
        name: str,
        description: str,
        llm: BaseLLM,
        system_prompt: str,
        tools: Optional[List[BaseTool]] = None,
        data_sources: Optional[Dict[str, Any]] = None,
    ):
        """Initialize specialist agent.

        Args:
            name: Agent identifier
            description: Human-readable description
            llm: LLM instance
            system_prompt: Base system prompt
            tools: Domain-specific tools (hidden from dispatcher)
            data_sources: Data sources this specialist has access to
        """
        super().__init__(name, description, llm, system_prompt, tools)
        self.data_sources = data_sources or {}
        self._pydantic_agent: Optional[Agent] = None
        self._setup_agent()

    def _setup_agent(self) -> None:
        """Set up the pydantic_ai Agent with tools."""
        from ..agent_processor import PydanticAIModelAdapter

        model = PydanticAIModelAdapter(self.llm, system_prompt=self._base_system_prompt)
        self._pydantic_agent = Agent(
            model=model,
            deps_type=ConversationContext,
        )

        # Register domain-specific tools
        for tool in self._tools:
            self._register_tool(tool)

    def _register_tool(self, tool: BaseTool) -> None:
        """Register a tool with the pydantic_ai agent.

        Args:
            tool: Tool to register
        """
        schema = tool.get_schema()
        tool_name = schema["name"]
        tool_description = schema["description"]
        
        # Check if tool has a request_model for better schema generation
        request_model = getattr(tool, "request_model", None)

        async def tool_wrapper(ctx: RunContext[ConversationContext], **kwargs) -> str:
            """Tool wrapper for PydanticAI integration."""
            context = ctx.deps
            
            # Handle both kwargs and request object
            if request_model and "request" in kwargs:
                params = kwargs["request"].model_dump()
            else:
                params = kwargs
                
            result = await tool.execute(context, **params)

            if result.success:
                return f"Result from tool '{tool_name}':\n" + (
                    result.message or str(result.data) or "Success (no output)"
                )
            else:
                return f"Error from tool '{tool_name}':\n" + (
                    result.error or "Unknown error"
                )

        tool_wrapper.__name__ = tool_name
        tool_wrapper.__doc__ = tool_description
        
        # Apply typed wrapper if request_model is available
        if request_model:
            async def typed_wrapper(ctx: RunContext[ConversationContext], request: request_model) -> str:
                return await tool_wrapper(ctx, request=request)
            
            typed_wrapper.__name__ = tool_name
            typed_wrapper.__doc__ = tool_description
            self._pydantic_agent.tool(typed_wrapper)
        else:
            self._pydantic_agent.tool(tool_wrapper)
            
        logger.debug(f"[{self.name}] Registered tool: {tool_name}")

    async def process(
        self,
        message: str,
        context: AgentContext
    ) -> AgentResult:
        """Process a message with structured input/output.

        Args:
            message: Delegated query (may be JSON from request model)
            context: Agent context

        Returns:
            AgentResult with response
        """
        start_time = time.time()
        tool_calls: List[str] = []

        try:
            # Get context-aware system prompt
            system_prompt = self.get_system_prompt(context)

            # Update model's system prompt
            self._pydantic_agent.model._system_prompt = system_prompt
            
            # Set trace on the model adapter if available
            if context.metadata.get("trace"):
                 self._pydantic_agent.model.set_trace(context.metadata.get("trace"))

            # Convert AgentContext to ConversationContext for tool compatibility
            conversation_context = ConversationContext(
                chat_id=context.chat_id,
                user_id=context.user_id,
                messages=[],  # Empty - specialist should use tools if needed
            )
            # Pass metadata through
            conversation_context.metadata = context.metadata

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
                f"[{self.name}] Processed in {processing_time:.2f}ms: "
                f"{response_text[:100]}..."
            )

            return AgentResult(
                success=True,
                response_text=response_text,
                structured_data=None,  # Subclasses can override to parse
                agent_name=self.name,
                trace_id=context.trace_id,
                tool_calls_made=tool_calls,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(f"[{self.name}] Processing failed: {e}", exc_info=True)
            processing_time = (time.time() - start_time) * 1000

            return AgentResult(
                success=False,
                response_text=f"I encountered an error while processing: {str(e)}",
                agent_name=self.name,
                trace_id=context.trace_id,
                tool_calls_made=tool_calls,
                processing_time_ms=processing_time,
            )

    @abstractmethod
    def get_system_prompt(self, context: AgentContext) -> str:
        """Get system prompt with injected context.

        Subclasses must implement this to provide domain-specific prompts.

        Args:
            context: Agent context for dynamic prompt generation

        Returns:
            Complete system prompt string
        """
        pass
