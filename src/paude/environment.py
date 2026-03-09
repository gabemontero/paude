"""Environment variable builder for paude containers."""

from __future__ import annotations


def build_environment(agent_name: str = "claude") -> dict[str, str]:
    """Build the environment variables to pass to the container.

    Delegates to the agent's build_environment() method.

    Args:
        agent_name: Agent name to use for environment building.

    Returns:
        Dictionary of environment variables.
    """
    from paude.agents import get_agent

    agent = get_agent(agent_name)
    return agent.build_environment()


def build_proxy_environment(proxy_name: str) -> dict[str, str]:
    """Build environment variables for proxy configuration.

    Args:
        proxy_name: Name of the proxy container.

    Returns:
        Dictionary of proxy environment variables.
    """
    proxy_url = f"http://{proxy_name}:3128"
    return {
        "HTTP_PROXY": proxy_url,
        "HTTPS_PROXY": proxy_url,
        "http_proxy": proxy_url,
        "https_proxy": proxy_url,
    }
