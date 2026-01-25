"""Prompt injection system for tools to contribute context to system prompt."""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

logger = logging.getLogger(__name__)


class BasePromptInjector(ABC):
    """
    Base class for prompt injectors that contribute context to system prompt.

    Prompt injectors allow tools and integrations to provide context that gets
    injected into the agent's system prompt at startup. This enables the agent
    to have awareness of available data sources without needing to call tools.

    Example:
        class NotionPromptInjector(BasePromptInjector):
            def get_context(self):
                return "User has 42 pages in Notion covering Projects and Notes."
    """

    def __init__(self, name: str, priority: int = 100):
        """
        Initialize injector.

        Args:
            name: Unique identifier for this injector
            priority: Order in which context is injected (lower = first, default 100)
        """
        self.name = name
        self.priority = priority

    @abstractmethod
    def get_context(self) -> Optional[str]:
        """
        Get context string to inject into system prompt.

        Returns:
            Context string or None if no context available.
            Returning None means this injector has nothing to contribute
            (e.g., data file doesn't exist yet).
        """
        pass

    def get_name(self) -> str:
        """Get injector name."""
        return self.name

    def get_priority(self) -> int:
        """Get injector priority."""
        return self.priority


class PromptInjectionRegistry:
    """
    Registry for collecting and managing prompt injectors.

    The registry collects context from all registered injectors and combines
    them into a single string that can be injected into the system prompt.

    Example:
        registry = PromptInjectionRegistry()
        registry.register(NotionPromptInjector())
        registry.register(CalendarPromptInjector())

        context = registry.collect_all_context()
        system_prompt = get_system_prompt(tool_context=context)
    """

    def __init__(self):
        """Initialize empty registry."""
        self._injectors: List[BasePromptInjector] = []

    def register(self, injector: BasePromptInjector) -> None:
        """
        Register a prompt injector.

        Args:
            injector: Injector instance to register
        """
        self._injectors.append(injector)
        logger.debug(f"Registered prompt injector: {injector.get_name()}")

    def collect_all_context(self) -> str:
        """
        Collect context from all registered injectors.

        Injectors are processed in priority order (lower priority first).
        Injectors that return None or raise exceptions are skipped.

        Returns:
            Combined context string from all injectors, or empty string
            if no injectors have context to contribute.
        """
        # Sort by priority (lower = first)
        sorted_injectors = sorted(self._injectors, key=lambda x: x.get_priority())

        contexts = []
        for injector in sorted_injectors:
            try:
                context = injector.get_context()
                if context:
                    contexts.append(context)
                    logger.debug(f"Injector '{injector.get_name()}' contributed context")
                else:
                    logger.debug(f"Injector '{injector.get_name()}' has no context")
            except Exception as e:
                logger.warning(f"Injector '{injector.get_name()}' failed: {e}")

        return "\n\n".join(contexts) if contexts else ""

    def get_injectors(self) -> List[BasePromptInjector]:
        """Get all registered injectors."""
        return list(self._injectors)

    def clear(self) -> None:
        """Clear all registered injectors."""
        self._injectors.clear()
