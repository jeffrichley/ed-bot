"""Test that a freeform chat message produces an ed-bot reply line in the app."""
import pytest

from ed_bot.cockpit.app import CockpitApp
from ed_bot.cockpit.widgets import ChatLog
from ed_bot.cockpit.models import DraftPayload
from textual.widgets import Static


def _make_app():
    async def draft_fn(*, number, **kw):
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question="q", body="b", confidence="HIGH")

    async def chat_fn(*, text, cwd, course_id):
        return f"you said: {text}"

    return CockpitApp(cwd=".", course_id=98559, draft_fn=draft_fn,
                      post_fn=None, is_answered_fn=None, fetch_events=None,
                      chat_fn=chat_fn)


@pytest.mark.anyio
async def test_freeform_chat_shows_ed_bot_reply():
    app = _make_app()
    async with app.run_test() as pilot:
        chat = app.query_one("#chat")
        chat.value = "what's the deadline?"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        log = app.query_one(ChatLog)
        text = "\n".join(str(s.content) for s in log.query(Static))
        assert "you" in text and "what's the deadline?" in text
        assert "ed-bot" in text and "you said: what's the deadline?" in text
