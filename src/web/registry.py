"""Subsection registry for web debug UI."""

from typing import Dict, List, Optional, Type
import logging

from .base import BaseSubsection

logger = logging.getLogger(__name__)

# Global registry instance
_registry: Optional["SubsectionRegistry"] = None


def get_registry() -> "SubsectionRegistry":
    """Get the global subsection registry."""
    global _registry
    if _registry is None:
        _registry = SubsectionRegistry()
    return _registry


def subsection(cls: Type[BaseSubsection]) -> Type[BaseSubsection]:
    """
    Decorator to register a subsection class.

    Usage:
        @subsection
        class MySubsection(BaseSubsection):
            ...
    """
    registry = get_registry()
    instance = cls()
    registry.register(instance)
    return cls


class SubsectionRegistry:
    """Registry for debug UI subsections."""

    def __init__(self):
        self._subsections: Dict[str, BaseSubsection] = {}

    def register(self, subsection_instance: BaseSubsection) -> None:
        """Register a subsection."""
        if subsection_instance.name in self._subsections:
            logger.warning(f"Overwriting subsection: {subsection_instance.name}")
        self._subsections[subsection_instance.name] = subsection_instance
        logger.debug(f"Registered subsection: {subsection_instance.name}")

    def get(self, name: str) -> Optional[BaseSubsection]:
        """Get subsection by name."""
        return self._subsections.get(name)

    def get_all(self) -> List[BaseSubsection]:
        """Get all subsections sorted by priority."""
        return sorted(self._subsections.values(), key=lambda s: s.priority)

    def get_metadata_list(self) -> List[Dict]:
        """Get metadata for all subsections."""
        return [s.get_metadata() for s in self.get_all()]
