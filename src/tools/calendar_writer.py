"""Google Calendar Writer tool."""

from datetime import datetime
from typing import Any, Dict, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .base import BaseTool, ToolResult
from ..context.models import ConversationContext

SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarWriterTool(BaseTool):
    """Tool for creating events in Google Calendar."""

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        service_account_email: Optional[str] = None,
        service_account_key: Optional[str] = None,
    ):
        """
        Initialize Calendar Writer tool.

        Args:
            credentials_path: Path to OAuth2 credentials JSON file
            service_account_email: Service account email (alternative auth)
            service_account_key: Service account key (alternative auth)
        """
        super().__init__(
            name="calendar_writer",
            description="Create events in Google Calendar. Requires title, start time, and optionally end time and description.",
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
        Create a calendar event.

        Args:
            context: Conversation context
            **kwargs: Must contain:
                - 'title' (str): Event title
                - 'start_time' (str): Start time in ISO format
                - 'end_time' (str, optional): End time in ISO format
                - 'description' (str, optional): Event description
                - 'location' (str, optional): Event location

        Returns:
            ToolResult with created event info
        """
        if "title" not in kwargs:
            return ToolResult(
                success=False,
                data=None,
                error="Missing required parameter: title",
            )

        if "start_time" not in kwargs:
            return ToolResult(
                success=False,
                data=None,
                error="Missing required parameter: start_time",
            )

        try:
            service = self._get_service()
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to authenticate with Google Calendar: {str(e)}",
            )

        title = kwargs["title"]
        start_time = kwargs["start_time"]
        end_time = kwargs.get("end_time")
        description = kwargs.get("description", "")
        location = kwargs.get("location", "")

        # If no end_time, default to 1 hour after start
        if not end_time:
            try:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                end_dt = start_dt.replace(hour=start_dt.hour + 1)
                end_time = end_dt.isoformat()
            except Exception:
                return ToolResult(
                    success=False,
                    data=None,
                    error="Invalid start_time format. Use ISO format (e.g., 2024-01-01T10:00:00Z)",
                )

        event = {
            "summary": title,
            "description": description,
            "location": location,
            "start": {
                "dateTime": start_time,
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": end_time,
                "timeZone": "UTC",
            },
        }

        try:
            created_event = (
                service.events().insert(calendarId="primary", body=event).execute()
            )

            return ToolResult(
                success=True,
                data={
                    "event_id": created_event.get("id"),
                    "title": title,
                    "start": start_time,
                    "end": end_time,
                    "html_link": created_event.get("htmlLink"),
                },
                message=f"Successfully created calendar event '{title}'",
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
                error=f"Failed to create calendar event: {str(e)}",
            )

    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema for pydantic_ai."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Event title",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time in ISO format (e.g., 2024-01-01T10:00:00Z)",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in ISO format (optional, defaults to 1 hour after start)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Event description (optional)",
                    },
                    "location": {
                        "type": "string",
                        "description": "Event location (optional)",
                    },
                },
                "required": ["title", "start_time"],
            },
        }

