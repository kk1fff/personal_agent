"""Agent registry for multi-agent orchestrator pattern."""

import logging
from typing import Dict, List, Optional

from .base import BaseAgent

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Central registry for sub-agents.

    The Dispatcher uses this registry to look up available specialists
    and generate agent descriptions for its system prompt.
    """

    def __init__(self):
        """Initialize empty registry."""
        self._agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Register an agent.

        Args:
            agent: Agent instance to register

        Raises:
            ValueError: If an agent with the same name is already registered
        """
        name = agent.get_name()
        if name in self._agents:
            raise ValueError(f"Agent '{name}' is already registered")

        self._agents[name] = agent
        logger.debug(f"Registered agent: {name}")

    def get(self, name: str) -> Optional[BaseAgent]:
        """Get an agent by name.

        Args:
            name: Agent identifier

        Returns:
            Agent instance or None if not found
        """
        return self._agents.get(name)

    def list_agents(self) -> List[str]:
        """Get list of registered agent names.

        Returns:
            List of agent identifiers
        """
        return list(self._agents.keys())

    def get_all(self) -> List[BaseAgent]:
        """Get all registered agents.

        Returns:
            List of all agent instances
        """
        return list(self._agents.values())

    def get_agent_descriptions(self) -> str:
        """Generate formatted descriptions of all agents for dispatcher prompt.

        Returns:
            Formatted string with agent names and descriptions
        """
        if not self._agents:
            return "No specialists available."

        lines = []
        for name, agent in self._agents.items():
            lines.append(f"- **{name}**: {agent.get_description()}")

        return "\n".join(lines)

    def unregister(self, name: str) -> bool:
        """Unregister an agent.

        Args:
            name: Agent identifier to remove

        Returns:
            True if agent was removed, False if not found
        """
        if name in self._agents:
            del self._agents[name]
            logger.debug(f"Unregistered agent: {name}")
            return True
        return False

    def clear(self) -> None:
        """Remove all registered agents."""
        self._agents.clear()
        logger.debug("Cleared all agents from registry")

    def __len__(self) -> int:
        """Get number of registered agents."""
        return len(self._agents)

    def __contains__(self, name: str) -> bool:
        """Check if an agent is registered."""
        return name in self._agents
