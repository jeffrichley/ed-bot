"""Tests for emit() — JSON-line output to stdout."""
import json
from ed_bot.watch.emit import emit


def test_emit_writes_single_json_line(capsys):
    emit("new_thread", thread_id=42, number=10, title="Hi", category="P1", url="https://e/1")
    captured = capsys.readouterr()
    line = captured.out.strip()
    assert "\n" not in line  # exactly one line
    payload = json.loads(line)
    assert payload["kind"] == "new_thread"
    assert payload["thread_id"] == 42
    assert payload["number"] == 10
    assert payload["title"] == "Hi"
    assert payload["category"] == "P1"
    assert payload["url"] == "https://e/1"
    assert "ts" in payload
    assert payload["ts"].endswith("+00:00")


def test_emit_error_event(capsys):
    emit("error", reason="api_unavailable_30m")
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["kind"] == "error"
    assert payload["reason"] == "api_unavailable_30m"
    assert "ts" in payload


def test_emit_terminates_with_newline(capsys):
    emit("recovered")
    assert capsys.readouterr().out.endswith("\n")


import pathlib


def test_emit_serializes_non_native_types_via_str(capsys):
    emit("new_thread", thread_id=1, path=pathlib.Path("/tmp/x"))
    import json
    payload = json.loads(capsys.readouterr().out)
    # pathlib.Path should serialize via str() instead of raising TypeError
    assert payload["path"] == str(pathlib.Path("/tmp/x"))
