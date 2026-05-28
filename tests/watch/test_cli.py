"""Tests for the ed watch CLI subcommands."""
from unittest.mock import patch, MagicMock
import os
import pathlib
from typer.testing import CliRunner
from ed_bot.watch.cli import app

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
