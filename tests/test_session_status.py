"""Tests for the session_status module."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from paude.session_status import (
    SessionActivity,
    _detect_state,
    _format_elapsed,
    _parse_elapsed_seconds,
    get_session_activity,
    parse_activity,
)


class TestParseElapsedSeconds:
    """Tests for _parse_elapsed_seconds."""

    def test_valid_timestamp(self) -> None:
        ts = str(int(time.time()) - 30)
        result = _parse_elapsed_seconds(ts)
        assert result is not None
        assert 29 <= result <= 31

    def test_invalid_timestamp(self) -> None:
        assert _parse_elapsed_seconds("not-a-number") is None

    def test_empty_string(self) -> None:
        assert _parse_elapsed_seconds("") is None

    def test_multiline_takes_first(self) -> None:
        ts = str(int(time.time()) - 60)
        result = _parse_elapsed_seconds(f"{ts}\nextra")
        assert result is not None
        assert 59 <= result <= 61


class TestFormatElapsed:
    """Tests for _format_elapsed."""

    def test_seconds_ago(self) -> None:
        assert _format_elapsed(30) == "30s ago"

    def test_minutes_ago(self) -> None:
        assert _format_elapsed(300) == "5m ago"

    def test_hours_ago(self) -> None:
        assert _format_elapsed(7200) == "2h ago"

    def test_days_ago(self) -> None:
        assert _format_elapsed(172800) == "2d ago"

    def test_just_now(self) -> None:
        assert _format_elapsed(-10) == "just now"

    def test_none(self) -> None:
        assert _format_elapsed(None) == "unknown"


class TestDetectState:
    """Tests for _detect_state."""

    def test_active_recent(self) -> None:
        assert _detect_state(30) == "Active"

    def test_idle_old(self) -> None:
        assert _detect_state(600) == "Idle"

    def test_active_boundary(self) -> None:
        assert _detect_state(119) == "Active"

    def test_idle_boundary(self) -> None:
        assert _detect_state(120) == "Idle"

    def test_none(self) -> None:
        assert _detect_state(None) == "Idle"


class TestParseActivity:
    """Tests for parse_activity."""

    def test_returns_active_with_elapsed(self) -> None:
        ts = str(int(time.time()) - 30)
        result = parse_activity(ts)
        assert isinstance(result, SessionActivity)
        assert result.state == "Active"
        assert result.elapsed_seconds is not None
        assert 29 <= result.elapsed_seconds <= 31

    def test_returns_idle_with_elapsed(self) -> None:
        ts = str(int(time.time()) - 300)
        result = parse_activity(ts)
        assert result.state == "Idle"
        assert result.elapsed_seconds is not None
        assert 299 <= result.elapsed_seconds <= 301

    def test_invalid_timestamp_returns_none_elapsed(self) -> None:
        result = parse_activity("garbage")
        assert result.elapsed_seconds is None
        assert result.last_activity == "unknown"


class TestGetSessionActivity:
    """Tests for get_session_activity."""

    def test_queries_tmux(self) -> None:
        mock_backend = MagicMock()
        ts = str(int(time.time()) - 30)
        mock_backend.exec_in_session.return_value = (0, f"{ts}\n", "")

        result = get_session_activity(mock_backend, "my-session")

        assert result.state == "Active"
        assert mock_backend.exec_in_session.call_count == 1

    def test_handles_tmux_failure(self) -> None:
        mock_backend = MagicMock()
        mock_backend.exec_in_session.return_value = (1, "", "no tmux")

        result = get_session_activity(mock_backend, "my-session")

        assert result.last_activity == "unknown"
        assert result.state == "Idle"
