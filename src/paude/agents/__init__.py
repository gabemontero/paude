"""Agent abstraction for CLI coding agents."""

from __future__ import annotations

from paude.agents.base import Agent, AgentConfig
from paude.agents.claude import ClaudeAgent

__all__ = ["Agent", "AgentConfig", "ClaudeAgent", "get_agent", "list_agents"]

_REGISTRY: dict[str, type] = {
    "claude": ClaudeAgent,
}


def get_agent(name: str) -> Agent:
    """Get an agent instance by name.

    Args:
        name: Agent name (e.g., "claude").

    Returns:
        Agent instance.

    Raises:
        ValueError: If agent name is not registered.
    """
    cls = _REGISTRY.get(name)
    if cls is None:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise ValueError(f"Unknown agent '{name}'. Available: {available}")
    return cls()  # type: ignore[no-any-return]


def list_agents() -> list[str]:
    """List all registered agent names.

    Returns:
        Sorted list of agent names.
    """
    return sorted(_REGISTRY.keys())
