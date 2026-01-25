"""Notion prompt injector for system prompt context injection."""

import json
import logging
from pathlib import Path
from typing import Optional

from ..agent.prompt_injection import BasePromptInjector

logger = logging.getLogger(__name__)


class NotionPromptInjector(BasePromptInjector):
    """
    Injects Notion workspace summary into the system prompt.

    Reads workspace information from data/notion/info.json (generated during indexing)
    and formats it for injection into the agent's system prompt. This allows the agent
    to know what content is available in the user's Notion without calling tools.

    Example output:
        ## Notion Workspace Context

        Your Notion workspace contains 42 indexed pages covering projects, notes, and ideas.

        **Indexed Workspaces:**
        - Personal: 42 pages covering Projects, Notes, Ideas
    """

    DEFAULT_INFO_PATH = "data/notion/info.json"

    def __init__(self, info_path: Optional[str] = None):
        """
        Initialize Notion prompt injector.

        Args:
            info_path: Path to info.json file (default: data/notion/info.json)
        """
        super().__init__(name="notion", priority=50)
        self.info_path = Path(info_path or self.DEFAULT_INFO_PATH)

    def get_context(self) -> Optional[str]:
        """
        Load Notion summary and format for system prompt injection.

        Returns:
            Formatted context string or None if no data available
        """
        if not self.info_path.exists():
            logger.debug(f"Notion info file not found: {self.info_path}")
            return None

        try:
            with open(self.info_path, "r") as f:
                data = json.load(f)

            summary = data.get("summary", "")
            workspaces = data.get("workspaces", [])

            if not summary and not workspaces:
                logger.debug("Notion info file is empty")
                return None

            # Format context section
            lines = ["## Notion Workspace Context"]
            lines.append("")

            if summary:
                lines.append(summary)
                lines.append("")

            if workspaces:
                lines.append("**Indexed Workspaces:**")
                for ws in workspaces:
                    name = ws.get("name", "Unknown")
                    page_count = ws.get("page_count", 0)
                    topics = ws.get("topics", [])
                    topic_str = ", ".join(topics[:5]) if topics else "various topics"
                    lines.append(f"- {name}: {page_count} pages covering {topic_str}")

            return "\n".join(lines)

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Notion info file: {e}")
            return None
        except Exception as e:
            logger.warning(f"Failed to load Notion context: {e}")
            return None
