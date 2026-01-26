"""Notion Agent-as-a-Tool wrapper."""

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from .base_agent_tool import BaseAgentTool
from ...agent.specialists.notion_models import SearchScope


class NotionQuery(BaseModel):
    """Structured request for Notion specialist.

    This model defines the interface between the Dispatcher
    and the Notion specialist agent.

    The primary parameter is `user_question` which captures the full
    intent of what the user wants to find. The specialist uses LLM-based
    intelligence to expand queries, re-rank results, and synthesize answers.
    """

    # Primary: User's actual question/intent (not just keywords)
    user_question: str = Field(
        default="",
        description=(
            "The user's full question or request in natural language. "
            "This should capture the intent, not just search keywords. "
            "Example: 'What are the key decisions from last week's project meeting?'"
        ),
    )

    # Context about what they need
    context_hint: Optional[str] = Field(
        default=None,
        description=(
            "Additional context about what information the user needs. "
            "Example: 'Looking for meeting notes', 'Need project details'"
        ),
    )

    # Search scope indicator
    search_scope: SearchScope = Field(
        default=SearchScope.PRECISE,
        description=(
            "How specific vs. broad the search should be. "
            "'precise' for specific documents, 'exploratory' for browsing, "
            "'comprehensive' for gathering from multiple sources."
        ),
    )

    # Temporal hints (optional)
    time_context: Optional[str] = Field(
        default=None,
        description="Time-related context like 'recent', 'last month', 'from 2024'",
    )

    # Maximum pages to consider for synthesis
    max_pages_to_analyze: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum pages to fetch and analyze for the answer",
    )

    # --- Backward Compatibility Fields ---
    # These are deprecated but still supported for backward compatibility

    search_term: Optional[str] = Field(
        default=None,
        description="[DEPRECATED] Use user_question instead. What to search for in Notion workspace.",
    )
    date_range: Optional[str] = Field(
        default=None,
        description="[DEPRECATED] Use time_context instead. Optional date filter like 'last week'",
    )
    read_full_content: bool = Field(
        default=True,
        description="[DEPRECATED] Content is now always fetched for analysis. Kept for compatibility.",
    )
    max_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="[DEPRECATED] Use max_pages_to_analyze instead.",
    )

    @model_validator(mode="before")
    @classmethod
    def handle_legacy_format(cls, values):
        """Handle backward compatibility with old NotionQuery format."""
        if isinstance(values, dict):
            # Map search_term to user_question if user_question not provided
            if values.get("search_term") and not values.get("user_question"):
                values["user_question"] = values["search_term"]

            # Map date_range to time_context
            if values.get("date_range") and not values.get("time_context"):
                values["time_context"] = values["date_range"]

            # Map max_results to max_pages_to_analyze
            if values.get("max_results") and not values.get("max_pages_to_analyze"):
                values["max_pages_to_analyze"] = min(values["max_results"], 10)

        return values


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
