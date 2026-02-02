"""Web debug UI subsections.

Subsections are automatically registered when this module is imported.
"""

from .config_viewer import ConfigViewerSubsection
from .log_viewer import LogViewerSubsection
from .conversation_debugger import ConversationDebuggerSubsection

__all__ = [
    "ConfigViewerSubsection",
    "LogViewerSubsection",
    "ConversationDebuggerSubsection",
]
