"""Tests for the chat transcript: your messages echo, ed-bot replies render."""
import pytest

from ed_bot.cockpit.app import CockpitApp
from ed_bot.cockpit.widgets import ChatLog
from ed_bot.cockpit.models import DraftPayload, ChatMessage
from textual.widgets import Static


def _make_app():
    async def draft_fn(*, number, **kw):
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question="q", body="b", confidence="HIGH")
    return CockpitApp(cwd=".", course_id=98559, draft_fn=draft_fn,
                      post_fn=None, is_answered_fn=None, fetch_events=None)


@pytest.mark.anyio
async def test_submitting_echoes_you_line():
    app = _make_app()
    async with app.run_test() as pilot:
        chat = app.query_one("#chat")
        # Textual 8.x: Input.Submitted only fires when the widget has focus.
        # Setting .value alone does not focus it; focus() + pause() is required.
        chat.focus()
        await pilot.pause()
        chat.value = "check the forum"
        await pilot.press("enter")
        await pilot.pause()
        log = app.query_one(ChatLog)
        text = "\n".join(str(s.content) for s in log.query(Static))
        assert "you" in text and "check the forum" in text


@pytest.mark.anyio
async def test_chat_message_emission_renders_ed_bot_line():
    app = _make_app()
    async with app.run_test() as pilot:
        app._emit(ChatMessage(role="ed-bot", text="4 threads need attention"))
        await pilot.pause()
        log = app.query_one(ChatLog)
        text = "\n".join(str(s.content) for s in log.query(Static))
        assert "ed-bot" in text and "4 threads need attention" in text
