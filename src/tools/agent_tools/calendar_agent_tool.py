"""Calendar Agent-as-a-Tool wrapper."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .base_agent_tool import BaseAgentTool


class CalendarQuery(BaseModel):
    """Structured request for Calendar specialist.

    This model defines the interface between the Dispatcher
    and the Calendar specialist agent.
    """

    action: Literal["read", "write"] = Field(
        ...,
        description="'read' to view events, 'write' to create/modify events"
    )
    time_range: Optional[str] = Field(
        default=None,
        description="Time range like 'tomorrow', 'next week', 'January 15'"
    )
    event_title: Optional[str] = Field(
        default=None,
        description="Title for creating a new event"
    )
    event_time: Optional[str] = Field(
        default=None,
        description="Start time for new event in natural language or ISO format"
    )
    event_duration: Optional[str] = Field(
        default=None,
        description="Duration like '1 hour', '30 minutes'"
    )
    event_description: Optional[str] = Field(
        default=None,
        description="Description or notes for the event"
    )
    event_location: Optional[str] = Field(
        default=None,
        description="Location for the event"
    )


class CalendarAgentTool(BaseAgentTool):
    """Tool wrapper for Calendar specialist agent.

    Exposes the Calendar specialist to the Dispatcher as a callable tool,
    using the CalendarQuery model for structured hand-off.
    """

    request_model = CalendarQuery

    def __init__(self, calendar_specialist: "CalendarSpecialist"):
        """Initialize Calendar agent tool.

        Args:
            calendar_specialist: The Calendar specialist agent instance
        """
        super().__init__(
            agent=calendar_specialist,
            request_model=CalendarQuery,
        )
