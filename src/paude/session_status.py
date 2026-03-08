"""Session activity detection via tmux state inspection."""

from __future__ import annotations

import time
from dataclasses import dataclass

from paude.backends.base import Backend


@dataclass
class SessionActivity:
    """Activity information for a running session.

    Attributes:
        last_activity: Human-readable time since last activity (e.g., "2m ago").
        state: Session state ("Working", "Idle", "Waiting for input", "Stopped").
        elapsed_seconds: Seconds since last activity, or None if unknown.
    """

    last_activity: str
    state: str
    elapsed_seconds: int | None = None


_TMUX_QUERY_CMD = (
    "tmux list-windows -t claude -F '#{window_activity}' 2>/dev/null; true"
)


def get_session_activity(backend: Backend, session_name: str) -> SessionActivity:
    """Query tmux state in a running session.

    Args:
        backend: Backend instance with exec_in_session method.
        session_name: Session name.

    Returns:
        SessionActivity with parsed state and timing.
    """
    rc, output, _ = backend.exec_in_session(session_name, _TMUX_QUERY_CMD)

    activity_ts = output.strip() if rc == 0 else ""
    return parse_activity(activity_ts)


def parse_activity(activity_timestamp: str) -> SessionActivity:
    """Parse tmux activity timestamp into human-readable state.

    Args:
        activity_timestamp: Unix timestamp string from tmux window_activity.

    Returns:
        SessionActivity with parsed state.
    """
    elapsed = _parse_elapsed_seconds(activity_timestamp)
    last_activity = _format_elapsed(elapsed)
    state = _detect_state(elapsed)
    return SessionActivity(
        last_activity=last_activity, state=state, elapsed_seconds=elapsed
    )


def _parse_elapsed_seconds(timestamp_str: str) -> int | None:
    """Parse a unix timestamp string into elapsed seconds since now.

    Returns:
        Elapsed seconds (may be negative if timestamp is in the future),
        or None if unparseable.
    """
    try:
        ts = int(timestamp_str.strip().split("\n")[0])
    except (ValueError, IndexError):
        return None
    return int(time.time()) - ts


def _format_elapsed(elapsed: int | None) -> str:
    """Format elapsed seconds as human-readable time (e.g., '2m ago').

    Args:
        elapsed: Seconds since last activity, or None if unknown.

    Returns:
        Human-readable elapsed time string, or "unknown" if None.
    """
    if elapsed is None:
        return "unknown"
    if elapsed < 0:
        return "just now"
    if elapsed < 60:
        return f"{elapsed}s ago"
    if elapsed < 3600:
        return f"{elapsed // 60}m ago"
    if elapsed < 86400:
        return f"{elapsed // 3600}h ago"
    return f"{elapsed // 86400}d ago"


def _detect_state(elapsed: int | None) -> str:
    """Detect session state from elapsed seconds.

    Active if activity within the last 2 minutes, Idle otherwise.
    """
    if elapsed is None:
        return "Idle"
    if elapsed < 120:
        return "Active"
    return "Idle"
