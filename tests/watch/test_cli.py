"""Tests for the ed watch CLI subcommands."""
from unittest.mock import patch, MagicMock
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
