"""Centralized tool registry."""

from typing import Dict, List, Optional

from .base import BaseTool
from ..config.config_schema import AppConfig


class ToolRegistry:
    """Centralized registry for all tools."""

    def __init__(self):
        """Initialize empty tool registry."""
        self._tools: Dict[str, BaseTool] = {}

    def register_tool(self, tool: BaseTool) -> None:
        """
        Register a tool in the registry.

        Args:
            tool: Tool instance to register
        """
        self._tools[tool.get_name()] = tool

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def get_all_tools(self) -> List[BaseTool]:
        """
        Get all registered tools.

        Returns:
            List of all registered tools
        """
        return list(self._tools.values())

    def initialize_tools(
        self, config: AppConfig, send_message_callback, context_manager=None
    ) -> None:
        """
        Initialize and register all tools based on configuration.

        Args:
            config: Application configuration
            send_message_callback: Callback function for sending messages
            context_manager: Optional ConversationContextManager for context retrieval
        """
        # Always register chat_reply tool
        from .chat_reply import ChatReplyTool

        chat_reply = ChatReplyTool(send_message_callback)
        self.register_tool(chat_reply)

        # Register context manager tool if provided
        if context_manager:
            from .context_manager import ContextManagerTool

            context_config = config.agent.context
            context_tool = ContextManagerTool(
                context_manager,
                max_history=context_config.max_history,
                time_gap_threshold_minutes=context_config.time_gap_threshold_minutes,
            )
            self.register_tool(context_tool)

        # Register Notion tools if configured
        if config.tools.notion and config.tools.notion.api_key:
            from .notion_reader import NotionReaderTool
            from .notion_writer import NotionWriterTool

            notion_reader = NotionReaderTool(config.tools.notion.api_key)
            notion_writer = NotionWriterTool(config.tools.notion.api_key)
            self.register_tool(notion_reader)
            self.register_tool(notion_writer)

        # Register Google Calendar tools if configured
        if config.tools.google_calendar:
            cal_config = config.tools.google_calendar
            if cal_config.credentials_path or (
                cal_config.service_account_email and cal_config.service_account_key
            ):
                from .calendar_reader import CalendarReaderTool
                from .calendar_writer import CalendarWriterTool

                calendar_reader = CalendarReaderTool(
                    credentials_path=cal_config.credentials_path,
                    service_account_email=cal_config.service_account_email,
                    service_account_key=cal_config.service_account_key,
                )
                calendar_writer = CalendarWriterTool(
                    credentials_path=cal_config.credentials_path,
                    service_account_email=cal_config.service_account_email,
                    service_account_key=cal_config.service_account_key,
                )
                self.register_tool(calendar_reader)
                self.register_tool(calendar_writer)

