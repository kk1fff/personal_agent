"""System prompts for multi-agent orchestrator pattern."""

from .dispatcher_prompt import DISPATCHER_PROMPT
from .notion_prompt import NOTION_SPECIALIST_PROMPT
from .calendar_prompt import CALENDAR_SPECIALIST_PROMPT
from .memory_prompt import MEMORY_SPECIALIST_PROMPT
from .chitchat_prompt import CHITCHAT_SPECIALIST_PROMPT

__all__ = [
    "DISPATCHER_PROMPT",
    "NOTION_SPECIALIST_PROMPT",
    "CALENDAR_SPECIALIST_PROMPT",
    "MEMORY_SPECIALIST_PROMPT",
    "CHITCHAT_SPECIALIST_PROMPT",
]
