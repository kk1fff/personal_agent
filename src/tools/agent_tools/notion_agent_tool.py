"""Notion Agent-as-a-Tool wrapper."""

from typing import Optional

from pydantic import BaseModel, Field

from .base_agent_tool import BaseAgentTool


class NotionQuery(BaseModel):
    """Structured request for Notion specialist.

    This model defines the interface between the Dispatcher
    and the Notion specialist agent.
    """

    search_term: str = Field(
        ...,
        description="What to search for in Notion workspace"
    )
    date_range: Optional[str] = Field(
        default=None,
        description="Optional date filter like 'last week', 'yesterday', 'this month'"
    )
    read_full_content: bool = Field(
        default=False,
        description="Whether to fetch full page content of the best match"
    )
    max_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of search results to return"
    )


class NotionAgentTool(BaseAgentTool):
    """Tool wrapper for Notion specialist agent.

    Exposes the Notion specialist to the Dispatcher as a callable tool,
    using the NotionQuery model for structured hand-off.
    """

    request_model = NotionQuery

    def __init__(self, notion_specialist: "NotionSpecialist"):
        """Initialize Notion agent tool.

        Args:
            notion_specialist: The Notion specialist agent instance
        """
        super().__init__(
            agent=notion_specialist,
            request_model=NotionQuery,
        )
