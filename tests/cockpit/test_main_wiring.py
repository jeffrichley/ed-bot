"""Tests for the entry-point wiring helpers (no live app run)."""
import pytest

from ed_bot.cockpit.__main__ import build_draft_fn, build_seed_event, build_chat_fn
from ed_bot.cockpit.models import WatcherEvent


def test_build_seed_event_targets_thread_number():
    ev = build_seed_event(222, 98559)
    assert isinstance(ev, WatcherEvent)
    assert ev.number == 222
    assert ev.kind == "new_thread"
    assert "98559" in ev.url and "222" in ev.url


@pytest.mark.anyio
async def test_build_draft_fn_delegates_to_agent():
    calls = {}

    async def fake_draft_thread(*, number, cwd, course_id):
        calls["number"] = number
        from ed_bot.cockpit.models import DraftPayload
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question="q", body="b", confidence="HIGH")

    draft_fn = build_draft_fn(cwd="/ed", draft_thread=fake_draft_thread)
    payload = await draft_fn(number=207, cwd="/ignored", course_id=98559)
    assert calls["number"] == 207
    assert payload.number == 207


@pytest.mark.anyio
async def test_build_chat_fn_accepts_history_and_forwards_it():
    """The real chat_fn must accept the `history` kwarg the loop passes, and
    forward it to chat_reply. (Regression: the loop calls chat_fn(..., history=)
    so a chat_fn without it raises TypeError live.)"""
    seen = {}

    async def fake_chat_reply(*, text, cwd, course_id, history):
        seen["history"] = history
        seen["text"] = text
        return "ok"

    chat_fn = build_chat_fn(cwd="/ed", chat_reply=fake_chat_reply)
    reply = await chat_fn(text="what is my color", course_id=98559,
                          history=[("you", "my color is purple")])
    assert reply == "ok"
    assert seen["history"] == [("you", "my color is purple")]
