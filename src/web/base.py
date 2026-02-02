"""Base class for web debug UI subsections."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class BaseSubsection(ABC):
    """
    Base class for debug web UI subsections.

    Each subsection represents a distinct panel in the web UI
    that can display information and receive live updates.

    Example:
        @subsection
        class TraceViewerSubsection(BaseSubsection):
            def __init__(self):
                super().__init__(
                    name="traces",
                    display_name="Request Traces",
                    priority=10
                )

            async def get_initial_data(self) -> Dict[str, Any]:
                return {"traces": []}

            async def get_html_template(self) -> str:
                return "<div>Trace content here</div>"
    """

    def __init__(
        self,
        name: str,
        display_name: str,
        priority: int = 100,
        icon: Optional[str] = None,
    ):
        """
        Initialize subsection.

        Args:
            name: Unique identifier (used in URL path)
            display_name: Human-readable name for UI
            priority: Display order (lower = first)
            icon: Optional emoji or icon character
        """
        self.name = name
        self.display_name = display_name
        self.priority = priority
        self.icon = icon or ""

    @abstractmethod
    async def get_initial_data(self) -> Dict[str, Any]:
        """
        Get initial data to populate the subsection.

        Called when subsection is first loaded.

        Returns:
            Dictionary of data for the template
        """
        pass

    @abstractmethod
    async def get_html_template(self) -> str:
        """
        Get HTML template for this subsection.

        The template can use Alpine.js directives for reactivity.

        Returns:
            HTML string
        """
        pass

    async def handle_action(
        self, action: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle an action from the frontend.

        Override to handle user interactions.

        Args:
            action: Action name
            data: Action payload

        Returns:
            Response data
        """
        logger.warning(f"Unhandled action '{action}' in {self.name}")
        return {"error": f"Unknown action: {action}"}

    def get_metadata(self) -> Dict[str, Any]:
        """Get subsection metadata for UI."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "priority": self.priority,
            "icon": self.icon,
        }
