"""Google Calendar Reader tool."""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .base import BaseTool, ToolResult
from ..context.models import ConversationContext

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


class CalendarReaderTool(BaseTool):
    """Tool for reading events from Google Calendar."""

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        service_account_email: Optional[str] = None,
        service_account_key: Optional[str] = None,
    ):
        """
        Initialize Calendar Reader tool.

        Args:
            credentials_path: Path to OAuth2 credentials JSON file
            service_account_email: Service account email (alternative auth)
            service_account_key: Service account key (alternative auth)
        """
        super().__init__(
            name="calendar_reader",
            description="Read events from Google Calendar. Can list upcoming events or search by date range.",
        )
        self.credentials_path = credentials_path
        self.service_account_email = service_account_email
        self.service_account_key = service_account_key
        self.service = None

    def _get_service(self):
        """Get or create Google Calendar service."""
        if self.service:
            return self.service

        creds = None

        # Try service account first
        if self.service_account_email and self.service_account_key:
            try:
                creds = ServiceAccountCredentials.from_service_account_info(
                    {
                        "type": "service_account",
                        "client_email": self.service_account_email,
                        "private_key": self.service_account_key,
                    },
                    scopes=SCOPES,
                )
            except Exception:
                pass

        # Fall back to OAuth2 credentials file
        if not creds and self.credentials_path:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
            except Exception:
                pass

        if not creds or not creds.valid:
            raise ValueError("Invalid Google Calendar credentials")

        self.service = build("calendar", "v3", credentials=creds)
        return self.service

    async def execute(
        self, context: ConversationContext, **kwargs
    ) -> ToolResult:
        """
        Read calendar events.

        Args:
            context: Conversation context
            **kwargs: Optional parameters:
                - 'max_results' (int): Maximum number of events (default: 10)
                - 'time_min' (str): Start time in ISO format
                - 'time_max' (str): End time in ISO format

        Returns:
            ToolResult with calendar events
        """
        try:
            service = self._get_service()
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to authenticate with Google Calendar: {str(e)}",
            )

        max_results = kwargs.get("max_results", 10)
        time_min = kwargs.get("time_min")
        time_max = kwargs.get("time_max")

        # Default to next 7 days if no time range specified
        if not time_min:
            time_min = datetime.utcnow().isoformat() + "Z"
        if not time_max:
            time_max = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"

        try:
            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])

            event_list = []
            for event in events:
                start = event["start"].get("dateTime", event["start"].get("date"))
                event_list.append(
                    {
                        "id": event.get("id"),
                        "summary": event.get("summary", "No title"),
                        "start": start,
                        "description": event.get("description", ""),
                        "location": event.get("location", ""),
                    }
                )

            return ToolResult(
                success=True,
                data={
                    "events": event_list,
                    "count": len(event_list),
                    "time_range": {"min": time_min, "max": time_max},
                },
                message=f"Found {len(event_list)} calendar events",
            )
        except HttpError as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Google Calendar API error: {str(e)}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to read calendar: {str(e)}",
            )

    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema for pydantic_ai."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of events to return (default: 10)",
                    },
                    "time_min": {
                        "type": "string",
                        "description": "Start time in ISO format (default: now)",
                    },
                    "time_max": {
                        "type": "string",
                        "description": "End time in ISO format (default: 7 days from now)",
                    },
                },
                "required": [],
            },
        }

