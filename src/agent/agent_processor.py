"""Agent processor using pydantic_ai."""

import logging
from typing import Any, Dict, List, Optional

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelRequest, TextPart, ToolCallPart
from pydantic_ai.models import Model, ModelMessage, ModelResponse, ModelSettings, ModelRequestParameters
from pydantic_ai.usage import RequestUsage

from ..context.models import ConversationContext
from ..llm.base import BaseLLM
from ..tools.base import BaseTool, ToolResult
from .prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

from ..debug import RequestTrace, TraceEventType


class PydanticAIModelAdapter(Model):
    """Adapter to use our BaseLLM with pydantic_ai."""

    def __init__(self, llm: BaseLLM, system_prompt: Optional[str] = None, agent_name: str = "agent"):
        """
        Initialize adapter.

        Args:
            llm: BaseLLM instance
            llm: BaseLLM instance
            system_prompt: System prompt for the model
            agent_name: Name of the agent for tracing (default: "agent")
        """
        self.llm = llm
        self._system_prompt = system_prompt or ""
        self.agent_name = agent_name
        self._trace: Optional[RequestTrace] = None
        super().__init__()

    def set_trace(self, trace: Optional[RequestTrace]):
        """Set the request trace for the current execution.

        Also propagates the trace to the underlying LLM for direct LLM calls.
        """
        self._trace = trace
        # Propagate trace to underlying LLM so direct calls are also traced
        if hasattr(self.llm, 'set_trace'):
            self.llm.set_trace(trace, source_name=self.agent_name)

    @property
    def system(self) -> str:
        """Get system prompt."""
        return self._system_prompt

    @property
    def model_name(self) -> str:
        """Get model name."""
        return self.llm.get_model_name()

    async def request(
        self,
        messages: List[ModelMessage],
        model_settings: Optional[ModelSettings] = None,
        model_request_parameters: Optional[ModelRequestParameters] = None,
    ) -> ModelResponse:
        """
        Make a request to the LLM.

        Args:
            messages: List of model messages
            model_settings: Optional model settings
            model_request_parameters: Optional request parameters

        Returns:
            ModelResponse with the generated text and/or tool calls
        """
        # Convert messages to a prompt string
        prompt_parts = []
        system_prompt = self._system_prompt

        for msg in messages:
            if isinstance(msg, ModelRequest):
                # Extract text content from the message parts
                if hasattr(msg, 'parts'):
                    for part in msg.parts:
                        if isinstance(part, TextPart):
                            prompt_parts.append(part.content)
                        elif hasattr(part, 'content'):
                            prompt_parts.append(part.content)
                        elif hasattr(part, 'text'):
                            prompt_parts.append(part.text)

        # Combine prompt parts
        user_prompt = "\n".join(prompt_parts) if prompt_parts else ""

        # Extract tools from model_request_parameters
        tools = None
        if model_request_parameters and model_request_parameters.function_tools:
            tools = [
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.parameters_json_schema,
                }
                for tool in model_request_parameters.function_tools
            ]

        # Log all content being sent to the LLM
        logger.debug("=" * 60)
        logger.debug("LLM REQUEST - Full content being sent to agent")
        logger.debug("=" * 60)
        logger.debug(f"Model: {self.model_name}")
        logger.debug("-" * 40)
        logger.debug("SYSTEM PROMPT:")
        logger.debug(system_prompt)
        logger.debug("-" * 40)
        logger.debug("USER PROMPT:")
        logger.debug(user_prompt)
        logger.debug("-" * 40)
        logger.debug("TOOLS:")
        logger.debug(tools)
        logger.debug("=" * 60)

        # Call the LLM with tools
        if self._trace:
            self._trace.add_event(
                TraceEventType.LLM_REQUEST,
                source=self.agent_name,
                target=self.model_name,
                content_summary=f"Sending request to LLM (Length: {len(user_prompt)})",
                metadata={
                    "model": self.model_name,
                    "tool_count": tools,
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt
                }
            )

        response = await self.llm.generate(
            user_prompt,
            system_prompt=system_prompt,
            tools=tools,
        )

        if self._trace:
            self._trace.add_event(
                TraceEventType.LLM_RESPONSE,
                source=self.model_name,
                target=self.agent_name,
                content_summary=f"Received response from LLM (Length: {len(response.text or '')})",
                metadata={
                    "tool_calls": response.tool_calls,
                    "response": response.text
                }
            )

        # Build response parts
        response_parts = []

        # Add tool call parts if present
        if response.tool_calls:
            for tc in response.tool_calls:
                response_parts.append(
                    ToolCallPart(
                        tool_name=tc.name,
                        args=tc.arguments,
                        tool_call_id=tc.id,
                    )
                )

        # Add text part if present
        if response.text:
            response_parts.append(TextPart(content=response.text))

        # Ensure at least one part exists
        if not response_parts:
            response_parts.append(TextPart(content=""))

        # Create usage (simplified - we don't have token counts from our LLM)
        usage = RequestUsage(
            input_tokens=0,  # We don't have token counting
            output_tokens=0,  # We don't have token counting
        )

        # Create and return ModelResponse
        return ModelResponse(
            parts=response_parts,
            usage=usage,
            model_name=self.model_name,
        )


class AgentResponse:
    """Response from agent processing."""

    def __init__(
        self,
        text: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        follow_up: bool = False,
    ):
        """
        Initialize agent response.

        Args:
            text: Response text
            tool_calls: List of tool calls made
            follow_up: Whether this is a follow-up question
        """
        self.text = text
        self.tool_calls = tool_calls or []
        self.follow_up = follow_up


class AgentProcessor:
    """Processes commands through pydantic_ai agent."""

    def __init__(
        self,
        llm: BaseLLM,
        tools: List[BaseTool],
        system_prompt: str = SYSTEM_PROMPT,
        agent_name: str = "agent",
    ):
        """
        Initialize agent processor.

        Args:
            llm: LLM instance
            tools: List of available tools
            system_prompt: System prompt for the agent
            agent_name: Name of the agent for tracing
        """
        self.llm = llm
        self.system_prompt = system_prompt
        self.agent_name = agent_name
        self.tools = {tool.get_name(): tool for tool in tools}

        # Create pydantic_ai agent with dependency injection
        model = PydanticAIModelAdapter(llm, system_prompt=system_prompt, agent_name=agent_name)
        self.agent = Agent(
            model=model,
            deps_type=ConversationContext,
        )

        # Register tools with the agent
        for tool in tools:
            self._register_tool(tool)

    def _register_tool(self, tool: BaseTool) -> None:
        """
        Register a tool with the pydantic_ai agent.

        Args:
            tool: Tool to register
        """
        schema = tool.get_schema()
        tool_name = schema["name"]
        tool_description = schema["description"]

        # Create wrapper that adapts BaseTool to PydanticAI signature
        async def tool_wrapper(ctx: RunContext[ConversationContext], **kwargs) -> str:
            """Tool wrapper for PydanticAI integration."""
            # Extract ConversationContext from RunContext
            context = ctx.deps
            
            # Trace tool execution if trace is available
            trace = None
            if hasattr(context, "metadata") and context.metadata and "trace" in context.metadata:
                trace = context.metadata["trace"]
                
            start_time = 0
            if trace:
                start_time = __import__("time").time()
                trace.add_event(
                    TraceEventType.TOOL_CALL,
                    source=self.agent_name,
                    target=tool_name,
                    content_summary=f"Calling tool: {tool_name}",
                    metadata=kwargs
                )

            # Execute the tool
            result = await tool.execute(context, **kwargs)
            
            # Trace completion
            if trace:
                duration = (__import__("time").time() - start_time) * 1000
                trace.add_event(
                    TraceEventType.TOOL_CALL,
                    source=tool_name,
                    target=self.agent_name,
                    content_summary=f"Tool result: {'Success' if result.success else 'Error'}",
                    duration_ms=duration,
                    metadata={"success": result.success, "result": result.message or str(result.data)}
                )

            # Convert ToolResult to string for PydanticAI

            # Convert ToolResult to string for PydanticAI
            if result.success:
                return "Result from tool '{}':\n".format(tool_name) + (result.message or str(result.data) or "Success (no output)")
            else:
                return "Error from tool '{}':\n".format(tool_name) + (result.error or 'Unknown error')

        # Set function metadata from schema
        tool_wrapper.__name__ = tool_name
        tool_wrapper.__doc__ = tool_description

        # Register with agent using decorator pattern
        self.agent.tool(tool_wrapper)

        logger.debug(f"Registered tool: {tool_name}")

    async def process_command(
        self, message: str, context: ConversationContext
    ) -> AgentResponse:
        """
        Process a user command through the agent.

        Args:
            message: User message
            context: Conversation context (metadata only, no automatic history)

        Returns:
            AgentResponse with result
        """
        # Log incoming command
        logger.debug("=" * 60)
        logger.debug("AGENT COMMAND - Processing user message")
        logger.debug("=" * 60)
        logger.debug(f"Chat ID: {context.chat_id}")
        logger.debug(f"User ID: {context.user_id}")
        logger.debug("-" * 40)
        logger.debug("USER MESSAGE:")
        logger.debug(message)
        logger.debug("=" * 60)

        try:
            # Inject trace if available in context
            if hasattr(context, "metadata") and "trace" in context.metadata:
                self.agent.model.set_trace(context.metadata["trace"])

            # Run agent with ConversationContext injected as dependency
            result = await self.agent.run(
                user_prompt=message,
                deps=context,
            )

            # Extract response text from RunResult
            # Note: May be .data or .output depending on version
            try:
                response_text = result.data
            except AttributeError:
                response_text = result.output  # Fallback for compatibility

            # Log agent response
            logger.debug("=" * 60)
            logger.debug("AGENT RESPONSE")
            logger.debug("=" * 60)
            logger.debug(response_text)
            logger.debug("=" * 60)

            # Determine if this is a follow-up question
            follow_up = any(
                keyword in response_text.lower()
                for keyword in ["?", "clarify", "which", "what", "when",
                              "where", "could you", "can you"]
            )

            return AgentResponse(
                text=response_text,
                tool_calls=[],  # PydanticAI handles tool calls internally
                follow_up=follow_up,
            )
        except Exception as e:
            logger.error(f"Error during agent command processing: {e}", exc_info=True)
            return AgentResponse(
                text="I'm having trouble processing your request right now. Please try again later.",
                tool_calls=[],
                follow_up=False,
            )

    async def handle_follow_up(
        self, question: str, context: ConversationContext
    ) -> AgentResponse:
        """
        Handle a follow-up question from the agent.

        Args:
            question: Follow-up question text
            context: Conversation context

        Returns:
            AgentResponse with follow-up question formatted for user
        """
        return AgentResponse(
            text=question,
            tool_calls=[],
            follow_up=True,
        )

