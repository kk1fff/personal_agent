"""Web debug UI subsections.

Subsections are automatically registered when this module is imported.
"""

from .log_viewer import LogViewerSubsection
from .config_viewer import ConfigViewerSubsection

__all__ = [
    "LogViewerSubsection",
    "ConfigViewerSubsection",
]
