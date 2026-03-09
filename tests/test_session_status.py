"""Tests for the session_status module."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from paude.session_status import (
    SessionActivity,
    WorkSummary,
    _detect_state,
    _format_elapsed,
    _parse_elapsed_seconds,
    format_work_summary,
    get_session_activity,
    get_session_enrichment,
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


class TestFormatWorkSummary:
    """Tests for format_work_summary."""

    def test_none_returns_empty(self) -> None:
        assert format_work_summary(None) == ""

    def test_detached_head(self) -> None:
        summary = WorkSummary(branch="HEAD", commits_ahead=0, latest_subject="")
        assert format_work_summary(summary) == "detached"

    def test_main_with_commits(self) -> None:
        summary = WorkSummary(
            branch="main", commits_ahead=3, latest_subject="Fix login bug"
        )
        assert format_work_summary(summary) == "Fix login bug (+3)"

    def test_main_with_commits_no_subject(self) -> None:
        summary = WorkSummary(branch="main", commits_ahead=3, latest_subject="")
        assert format_work_summary(summary) == "(+3)"

    def test_feature_branch_with_commits(self) -> None:
        summary = WorkSummary(
            branch="feat-auth", commits_ahead=2, latest_subject="Add OAuth"
        )
        assert format_work_summary(summary) == "feat-auth Add OAuth (+2)"

    def test_feature_branch_no_commits(self) -> None:
        summary = WorkSummary(branch="feat-auth", commits_ahead=0, latest_subject="")
        assert format_work_summary(summary) == "feat-auth"

    def test_feature_branch_commits_no_subject(self) -> None:
        summary = WorkSummary(branch="feat-auth", commits_ahead=5, latest_subject="")
        assert format_work_summary(summary) == "feat-auth (+5)"

    def test_main_clean(self) -> None:
        summary = WorkSummary(branch="main", commits_ahead=0, latest_subject="")
        assert format_work_summary(summary) == ""

    def test_master_clean(self) -> None:
        summary = WorkSummary(branch="master", commits_ahead=0, latest_subject="")
        assert format_work_summary(summary) == ""

    def test_truncation(self) -> None:
        summary = WorkSummary(
            branch="very-long-feature-branch",
            commits_ahead=5,
            latest_subject="This is a very long commit message that exceeds the limit",
        )
        result = format_work_summary(summary, max_width=40)
        assert len(result) == 40
        assert result.endswith("...")

    def test_exact_max_width_no_truncation(self) -> None:
        summary = WorkSummary(branch="br", commits_ahead=1, latest_subject="X")
        result = format_work_summary(summary, max_width=100)
        assert "..." not in result


class TestGetSessionEnrichment:
    """Tests for get_session_enrichment."""

    def test_parses_combined_output(self) -> None:
        mock_backend = MagicMock()
        ts = str(int(time.time()) - 30)
        mock_backend.exec_in_session.return_value = (
            0,
            f"{ts}\nBRANCH:feat-auth\nAHEAD:3\nSUBJECT:Fix login bug\n",
            "",
        )

        activity, summary = get_session_enrichment(mock_backend, "my-session")

        assert activity.state == "Active"
        assert summary is not None
        assert summary.branch == "feat-auth"
        assert summary.commits_ahead == 3
        assert summary.latest_subject == "Fix login bug"
        assert mock_backend.exec_in_session.call_count == 1

    def test_returns_idle_and_none_on_failure(self) -> None:
        mock_backend = MagicMock()
        mock_backend.exec_in_session.return_value = (1, "", "error")

        activity, summary = get_session_enrichment(mock_backend, "my-session")

        assert activity.state == "Idle"
        assert summary is None

    def test_handles_missing_ahead_count(self) -> None:
        mock_backend = MagicMock()
        ts = str(int(time.time()) - 30)
        mock_backend.exec_in_session.return_value = (
            0,
            f"{ts}\nBRANCH:main\nAHEAD:\nSUBJECT:\n",
            "",
        )

        activity, summary = get_session_enrichment(mock_backend, "my-session")

        assert summary is not None
        assert summary.commits_ahead == 0
        assert summary.latest_subject == ""

    def test_returns_none_summary_on_empty_branch(self) -> None:
        mock_backend = MagicMock()
        ts = str(int(time.time()) - 30)
        mock_backend.exec_in_session.return_value = (
            0,
            f"{ts}\nBRANCH:\nAHEAD:0\nSUBJECT:\n",
            "",
        )

        activity, summary = get_session_enrichment(mock_backend, "my-session")

        assert activity.state == "Active"
        assert summary is None
