"""Tests for the cockpit Pydantic contract."""
import pytest
from pydantic import ValidationError

from ed_bot.cockpit.models import UserCommand, WatcherEvent


def test_user_command_minimal():
    cmd = UserCommand(intent="check_forum")
    assert cmd.intent == "check_forum"
    assert cmd.thread is None
    assert cmd.text is None


def test_user_command_with_thread_and_text():
    cmd = UserCommand(intent="edit", thread=207, text="make it more Socratic")
    assert cmd.thread == 207
    assert cmd.text == "make it more Socratic"


def test_user_command_rejects_unknown_intent():
    with pytest.raises(ValidationError):
        UserCommand(intent="frobnicate")


def test_watcher_event_roundtrip():
    ev = WatcherEvent(
        kind="new_thread",
        thread_id=8104866,
        number=207,
        title="Figure 1 graph",
        category="Project 1 | Martingale",
        url="https://edstem.org/us/courses/98559/discussion/8104866",
    )
    assert ev.number == 207
    assert ev.kind == "new_thread"


def test_watcher_event_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        WatcherEvent(
            kind="meteor_strike",
            thread_id=1, number=1, title="x", category="y", url="z",
        )
