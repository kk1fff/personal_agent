"""Web debug UI module for Personal Agent System."""

from .base import BaseSubsection
from .registry import SubsectionRegistry, get_registry, subsection
from .server import WebDebugServer
from .websocket_manager import ConnectionManager

# Import subsections to trigger registration
from . import subsections

__all__ = [
    "BaseSubsection",
    "SubsectionRegistry",
    "get_registry",
    "subsection",
    "WebDebugServer",
    "ConnectionManager",
]
