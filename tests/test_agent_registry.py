"""Tests for agent registry."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from src.agent.registry import AgentRegistry
from src.agent.base import BaseAgent, AgentContext, AgentResult


class MockAgent(BaseAgent):
    """Mock agent for testing."""

    def __init__(self, name: str, description: str):
        super().__init__(
            name=name,
            description=description,
            llm=MagicMock(),
            system_prompt="Test prompt",
            tools=[],
        )

    async def process(self, message: str, context: AgentContext) -> AgentResult:
        return AgentResult(
            success=True,
            response_text="Mock response",
            agent_name=self.name,
            trace_id=context.trace_id,
        )

    def get_system_prompt(self, context: AgentContext) -> str:
        return self._base_system_prompt


@pytest.fixture
def registry():
    """Create empty agent registry."""
    return AgentRegistry()


@pytest.fixture
def mock_agent():
    """Create mock agent."""
    return MockAgent("test_agent", "A test agent")


def test_register_agent(registry, mock_agent):
    """Test registering an agent."""
    registry.register(mock_agent)
    assert "test_agent" in registry
    assert len(registry) == 1


def test_register_duplicate_raises(registry, mock_agent):
    """Test registering duplicate agent raises error."""
    registry.register(mock_agent)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(mock_agent)


def test_get_agent(registry, mock_agent):
    """Test getting an agent by name."""
    registry.register(mock_agent)

    retrieved = registry.get("test_agent")
    assert retrieved is mock_agent


def test_get_nonexistent_agent(registry):
    """Test getting nonexistent agent returns None."""
    result = registry.get("nonexistent")
    assert result is None


def test_list_agents(registry):
    """Test listing registered agents."""
    agent1 = MockAgent("agent1", "First agent")
    agent2 = MockAgent("agent2", "Second agent")

    registry.register(agent1)
    registry.register(agent2)

    agents = registry.list_agents()
    assert len(agents) == 2
    assert "agent1" in agents
    assert "agent2" in agents


def test_get_all(registry):
    """Test getting all agents."""
    agent1 = MockAgent("agent1", "First agent")
    agent2 = MockAgent("agent2", "Second agent")

    registry.register(agent1)
    registry.register(agent2)

    agents = registry.get_all()
    assert len(agents) == 2
    assert agent1 in agents
    assert agent2 in agents


def test_get_agent_descriptions(registry):
    """Test getting formatted agent descriptions."""
    agent1 = MockAgent("agent1", "First test agent")
    agent2 = MockAgent("agent2", "Second test agent")

    registry.register(agent1)
    registry.register(agent2)

    descriptions = registry.get_agent_descriptions()
    assert "agent1" in descriptions
    assert "First test agent" in descriptions
    assert "agent2" in descriptions
    assert "Second test agent" in descriptions


def test_get_agent_descriptions_empty(registry):
    """Test getting descriptions when no agents registered."""
    descriptions = registry.get_agent_descriptions()
    assert descriptions == "No specialists available."


def test_unregister_agent(registry, mock_agent):
    """Test unregistering an agent."""
    registry.register(mock_agent)
    assert len(registry) == 1

    result = registry.unregister("test_agent")
    assert result is True
    assert len(registry) == 0


def test_unregister_nonexistent(registry):
    """Test unregistering nonexistent agent."""
    result = registry.unregister("nonexistent")
    assert result is False


def test_clear_registry(registry):
    """Test clearing all agents."""
    agent1 = MockAgent("agent1", "First agent")
    agent2 = MockAgent("agent2", "Second agent")

    registry.register(agent1)
    registry.register(agent2)
    assert len(registry) == 2

    registry.clear()
    assert len(registry) == 0


def test_contains(registry, mock_agent):
    """Test checking if agent is registered."""
    assert "test_agent" not in registry

    registry.register(mock_agent)
    assert "test_agent" in registry
