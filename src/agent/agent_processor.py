"""Agent processor using pydantic_ai."""

import logging
from typing import Any, Dict, List, Optional

from pydantic_ai import Agent
from pydantic_ai.messages import ModelRequest, TextPart
from pydantic_ai.models import Model, ModelMessage, ModelResponse, ModelSettings, ModelRequestParameters
from pydantic_ai.usage import RequestUsage

from ..context.models import ConversationContext
from ..llm.base import BaseLLM
from ..tools.base import BaseTool, ToolResult
from .prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class PydanticAIModelAdapter(Model):
    """Adapter to use our BaseLLM with pydantic_ai."""

    def __init__(self, llm: BaseLLM, system_prompt: Optional[str] = None):
        """
        Initialize adapter.

        Args:
            llm: BaseLLM instance
            system_prompt: System prompt for the model
        """
        self.llm = llm
        self._system_prompt = system_prompt or ""
        super().__init__()

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
            ModelResponse with the generated text
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

        # Call the LLM
        response_text = await self.llm.generate(
            user_prompt,
            system_prompt=system_prompt,
        )

        # Create response parts (TextPart uses 'content' not 'text')
        response_parts = [TextPart(content=response_text)]

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
    ):
        """
        Initialize agent processor.

        Args:
            llm: LLM instance
            tools: List of available tools
            system_prompt: System prompt for the agent
        """
        self.llm = llm
        self.system_prompt = system_prompt
        self.tools = {tool.get_name(): tool for tool in tools}

        # Create pydantic_ai agent
        model = PydanticAIModelAdapter(llm, system_prompt=system_prompt)
        self.agent = Agent(
            model=model,
        )

        # Register tools with the agent
        for tool in tools:
            self._register_tool(tool)

    def _register_tool(self, tool: BaseTool) -> None:
        """
        Register a tool with the agent.

        Args:
            tool: Tool to register
        """
        # Store tool for manual execution
        # pydantic_ai tool registration will be handled dynamically
        # when processing commands with context
        pass

    async def process_command(
        self, message: str, context: ConversationContext
    ) -> AgentResponse:
        """
        Process a user command through the agent.

        Args:
            message: User message
            context: Conversation context

        Returns:
            AgentResponse with result
        """
        # Format conversation history for context
        conversation_history = context.format_for_llm()
        if conversation_history:
            full_prompt = f"{conversation_history}\n\nUser: {message}\nAssistant:"
        else:
            full_prompt = message

        try:
            # Create tool functions with context injected
            tool_functions = {}
            for tool_name, tool in self.tools.items():
                async def create_tool_func(tool_instance):
                    async def tool_func(**kwargs) -> str:
                        result = await tool_instance.execute(context, **kwargs)
                        if result.success:
                            if result.message:
                                return result.message
                            return str(result.data)
                        else:
                            return f"Error: {result.error}"

                    return tool_func

                tool_functions[tool_name] = await create_tool_func(tool)

            # Register tools with agent for this run
            # Note: pydantic_ai may require different registration
            # This is a simplified approach - in practice, you may need to
            # use pydantic_ai's tool decorator or function registration API

            # For now, we'll use a simpler approach: call LLM directly
            # and handle tool calls manually if needed
            response_text = await self.llm.generate(
                full_prompt, system_prompt=self.system_prompt
            )

            # Simple tool call detection (can be enhanced)
            tool_calls = []
            if any(tool_name in response_text.lower() for tool_name in self.tools.keys()):
                # Tool might have been mentioned, but actual tool execution
                # would need to be parsed from LLM response or handled by pydantic_ai
                pass

            # Determine if this is a follow-up question
            follow_up = any(
                keyword in response_text.lower()
                for keyword in ["?", "clarify", "which", "what", "when", "where", "could you", "can you"]
            )

            return AgentResponse(
                text=response_text,
                tool_calls=tool_calls,
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

