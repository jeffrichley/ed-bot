"""Tests for chat input and hotkeys driving the loop."""
import pytest

from ed_bot.cockpit.app import CockpitApp
from ed_bot.cockpit.widgets import DraftViewer
from ed_bot.cockpit.models import WatcherEvent, DraftPayload, ActionResult


def _make_app(posted):
    async def draft_fn(*, number, **kw):
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question="q", body="clean body", confidence="HIGH")

    async def post_fn(*, thread_id, number, body, post_kind, target_comment_id):
        posted.append(number)
        return ActionResult(thread_id=thread_id, ok=True, posted_id=9,
                            accepted=True, message="ok")

    async def is_answered_fn(thread_id):
        return False

    return CockpitApp(cwd=".", course_id=98559, draft_fn=draft_fn,
                      post_fn=post_fn, is_answered_fn=is_answered_fn,
                      fetch_events=None)


@pytest.mark.anyio
async def test_typing_open_then_chat_post_it_posts():
    posted = []
    app = _make_app(posted)
    async with app.run_test() as pilot:
        await app.inject_event(WatcherEvent(
            kind="new_thread", thread_id=8100207, number=207,
            title="Figure 1 graph", category="Project 1 | Martingale", url="u"))
        await pilot.pause()
        chat = app.query_one("#chat")
        chat.value = "open 207"
        await pilot.press("enter")
        await pilot.pause()
        assert "clean body" in str(app.query_one(DraftViewer).content)
        chat.value = "post it"
        await pilot.press("enter")
        await pilot.pause()
        assert posted == [207]


@pytest.mark.anyio
async def test_hotkey_a_approves_active_thread():
    posted = []
    app = _make_app(posted)
    async with app.run_test() as pilot:
        await app.inject_event(WatcherEvent(
            kind="new_thread", thread_id=8100207, number=207,
            title="t", category="Project 1 | Martingale", url="u"))
        await pilot.pause()
        chat = app.query_one("#chat")
        chat.value = "open 207"
        await pilot.press("enter")
        await pilot.pause()
        app.set_focus(None)
        await pilot.press("a")
        await pilot.pause()
        assert posted == [207]
