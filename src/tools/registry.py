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
        self, config: AppConfig, context_manager=None
    ) -> None:
        """
        Initialize and register all tools based on configuration.

        Args:
            config: Application configuration
            context_manager: Optional ConversationContextManager for context retrieval
        """
        # Register context manager tool if provided
        if context_manager:
            from .context_manager import ContextManagerTool

            context_tool = ContextManagerTool(
                context_manager
            )
            self.register_tool(context_tool)

        # Register Notion search tool if configured
        if config.tools.notion and config.tools.notion.api_key:
            try:
                from ..memory.vector_store import VectorStore
                from ..memory.embeddings import EmbeddingGenerator
                from .notion_search import NotionSearchTool

                # Initialize vector store for Notion index
                vector_store = VectorStore(
                    db_path=config.database.vector_db_path,
                    collection_name=config.tools.notion.index_collection,
                )
                embedding_generator = EmbeddingGenerator()

                notion_search = NotionSearchTool(
                    api_key=config.tools.notion.api_key,
                    vector_store=vector_store,
                    embedding_generator=embedding_generator,
                    default_results=config.tools.notion.search_results_default,
                )
                self.register_tool(notion_search)
            except ImportError as e:
                # ChromaDB or sentence-transformers not installed
                import logging
                logging.getLogger(__name__).warning(
                    f"Notion search tool not available: {e}"
                )

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

