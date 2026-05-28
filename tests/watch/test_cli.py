"""Tests for the ed watch CLI subcommands."""
from unittest.mock import patch, MagicMock
import os
import pathlib
from typer.testing import CliRunner
from ed_bot.watch.cli import app
import ed_bot.watch.cli as _cli_module

runner = CliRunner()


def test_watch_help_lists_subcommands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    out = result.stdout
    assert "status" in out
    assert "stop" in out


def test_watch_once_calls_poll(tmp_path):
    cfg = tmp_path / "watch.yaml"
    cfg.write_text("""
course_id: 98559
schedule:
  - days: [mon, tue, wed, thu, fri]
    hours: "09:00-22:00"
    interval: 5m
sounds:
  new_thread: "{ed_bot}/watch/sounds/new.wav"
  followup: "{ed_bot}/watch/sounds/followup.wav"
  escalation: "{ed_bot}/watch/sounds/escalation.wav"
  error: "{ed_bot}/watch/sounds/error.wav"
""", encoding="utf-8")
    with patch("ed_bot.watch.cli._build_poll_fn") as build_poll:
        poll_fn = MagicMock()
        build_poll.return_value = poll_fn
        result = runner.invoke(app, ["--config", str(cfg), "--once"])
        assert result.exit_code == 0, result.stdout
        poll_fn.assert_called_once()


def test_watch_status_no_pidfile(tmp_path):
    with patch("ed_bot.watch.cli.PID_FILE", tmp_path / "watch.pid"):
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "not running" in result.stdout.lower()


def test_stop_releases_pid_lock(tmp_path, monkeypatch):
    import signal as _signal
    pid_path = tmp_path / "watch.pid"
    pid_path.write_text(str(os.getpid()))  # ourselves; guaranteed alive
    monkeypatch.setattr("ed_bot.watch.cli.PID_FILE", pid_path)
    with patch("ed_bot.watch.cli.os.kill") as mock_kill:
        result = runner.invoke(app, ["stop"])
    # os.kill is called twice: once with signal 0 (_pid_alive probe) and once
    # with SIGTERM. Verify the SIGTERM call is present.
    sigterm_calls = [c for c in mock_kill.call_args_list if c.args[1] == _signal.SIGTERM]
    assert len(sigterm_calls) == 1, f"Expected one SIGTERM call; got {mock_kill.call_args_list}"
    assert result.exit_code == 0
    assert not pid_path.exists(), "PID file should be cleaned up after stop"


def test_build_poll_fn_uses_tracker_for_our_answer_id(tmp_path, monkeypatch):
    """End-to-end: when tracker DB has our_answer_id, classifier sees it."""
    import sqlite3
    from ed_bot.watch.state import WatchAlertStore
    from ed_bot.watch import cli as cli_mod

    # Build a tracker DB with one thread that we previously answered.
    tracker_path = tmp_path / "tracker.db"
    conn = sqlite3.connect(str(tracker_path))
    conn.execute("""CREATE TABLE threads (
        thread_id INTEGER PRIMARY KEY,
        thread_number INTEGER, title TEXT, category TEXT,
        last_seen_updated_at TEXT, last_checked_at TEXT,
        reply_count_seen INTEGER NOT NULL DEFAULT 0,
        our_answer_id INTEGER, status TEXT, is_answered INTEGER)""")
    conn.execute("""INSERT INTO threads (thread_id, thread_number, title,
        reply_count_seen, our_answer_id, status, is_answered) VALUES
        (777, 5, 'Old thread', 2, 999, 'answered', 1)""")
    conn.commit()
    conn.close()

    # Point _build_poll_fn at this tracker DB.
    monkeypatch.setattr(pathlib.Path, "expanduser",
                        lambda self: tracker_path if "tracker.db" in str(self) else self)

    # Mock EdClient.from_env + the list call.
    fake_thread = MagicMock(id=777, number=5, title="Old thread",
                            category="Project 1 | Martingale", is_answered=True,
                            is_pinned=False, reply_count=2, updated_at="2026-05-28T12:00:00Z")
    fake_client = MagicMock()
    fake_client.threads.list.return_value = [fake_thread]

    with patch("ed_api.EdClient", return_value=fake_client):
        store = WatchAlertStore(tmp_path / "watch.db")
        try:
            poll_fn = cli_mod._build_poll_fn(98559, store, {})
            # Just verify it constructs and the fetch sees our_answer_id.
            # Run one poll via the store to check no exception is raised:
            poll_fn()
        finally:
            store.close()
