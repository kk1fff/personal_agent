"""Base class for Agent-as-a-Tool pattern."""

import logging
from datetime import datetime
from typing import Any, Dict, Type

from pydantic import BaseModel

from ..base import BaseTool, ToolResult
from ...context.models import ConversationContext
from ...agent.base import AgentContext, BaseAgent

logger = logging.getLogger(__name__)


class BaseAgentTool(BaseTool):
    """Wraps a specialist agent as a tool for the Dispatcher.

    This implements the Agent-as-a-Tool pattern where:
    1. Dispatcher sees a tool interface (name, description, parameters)
    2. Tool internally delegates to a full specialist agent
    3. Specialist's internal tool calls are hidden from Dispatcher

    The structured hand-off is enforced via Pydantic models.
    """

    # Subclasses must define this
    request_model: Type[BaseModel]

    def __init__(
        self,
        agent: BaseAgent,
        request_model: Type[BaseModel],
    ):
        """Initialize agent tool wrapper.

        Args:
            agent: The specialist agent to wrap
            request_model: Pydantic model defining the request schema
        """
        super().__init__(
            name=f"delegate_to_{agent.get_name()}",
            description=self._build_description(agent),
        )
        self.agent = agent
        self.request_model = request_model

    def _build_description(self, agent: BaseAgent) -> str:
        """Build tool description from agent.

        Args:
            agent: The wrapped agent

        Returns:
            Tool description string
        """
        return (
            f"Delegate this request to the {agent.get_name()} specialist. "
            f"{agent.get_description()}"
        )

    async def execute(
        self,
        context: ConversationContext,
        **kwargs
    ) -> ToolResult:
        """Execute by delegating to the wrapped agent.

        Args:
            context: Conversation context from dispatcher
            **kwargs: Request parameters matching request_model

        Returns:
            ToolResult with specialist's response
        """
        try:
            # Validate and parse request using Pydantic model
            request = self.request_model(**kwargs)
            logger.debug(
                f"Delegating to {self.agent.get_name()}: {request.model_dump()}"
            )

            # Convert ConversationContext to AgentContext
            agent_context = AgentContext(
                chat_id=context.chat_id,
                user_id=context.user_id,
                session_id=str(context.chat_id),
                message_history=[
                    {"role": m.role, "content": m.message_text}
                    for m in context.messages
                ],
                metadata=getattr(context, "metadata", {}),
            )

            # Create child trace if parent has one
            if agent_context.metadata.get("trace"):
                agent_context = agent_context.with_child_trace()

            # Record delegation start time
            start_time = datetime.now()

            # Delegate to specialist agent
            result = await self.agent.process(
                message=request.model_dump_json(),
                context=agent_context,
            )

            # Calculate processing time
            processing_time_ms = (
                datetime.now() - start_time
            ).total_seconds() * 1000

            logger.debug(
                f"Specialist {self.agent.get_name()} responded in "
                f"{processing_time_ms:.2f}ms: {result.response_text[:100]}..."
            )

            return ToolResult(
                success=result.success,
                data=result.structured_data,
                message=result.response_text,
            )

        except Exception as e:
            logger.error(
                f"Agent delegation to {self.agent.get_name()} failed: {e}",
                exc_info=True
            )
            return ToolResult(
                success=False,
                data=None,
                error=f"Agent delegation failed: {str(e)}",
            )

    def get_schema(self) -> Dict[str, Any]:
        """Generate schema from Pydantic request model.

        Returns:
            Tool schema dictionary for pydantic_ai registration
        """
        json_schema = self.request_model.model_json_schema()

        # Extract parameters from the JSON schema
        parameters = {
            "type": "object",
            "properties": json_schema.get("properties", {}),
            "required": json_schema.get("required", []),
        }

        return {
            "name": self.name,
            "description": self.description,
            "parameters": parameters,
        }
