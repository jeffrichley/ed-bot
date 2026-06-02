"""Open-in-browser action and the 'return focus to chat after selecting' fix."""
import pytest
from textual.widgets import Input

from ed_bot.cockpit.app import CockpitApp
from ed_bot.cockpit.widgets import QueueRail
from ed_bot.cockpit.models import WatcherEvent, DraftPayload

pytestmark = pytest.mark.anyio


def _make_app():
    async def draft_fn(*, number, **kw):
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question=f"q{number}", body=f"body {number}",
                            confidence="HIGH")
    return CockpitApp(cwd=".", course_id=98559, draft_fn=draft_fn,
                      post_fn=None, is_answered_fn=None, fetch_events=None)


async def _seed_item(app, pilot, number):
    await app.inject_event(WatcherEvent(
        kind="new_thread", thread_id=8100000 + number, number=number,
        title=f"t{number}", category="Project 1 | Martingale", url="u"))
    await pilot.pause()


async def test_selecting_thread_returns_focus_to_chat():
    app = _make_app()
    async with app.run_test() as pilot:
        await _seed_item(app, pilot, 207)
        rail = app.query_one(QueueRail)
        rail.focus()
        await pilot.pause()
        assert app.focused is rail  # queue has focus while navigating
        rail.highlighted = 0
        await pilot.press("enter")
        await pilot.pause()
        # After selecting, focus is back on the chat input so typing works.
        assert app.focused is app.query_one("#chat", Input)


async def test_thread_url_uses_global_thread_id_and_course():
    app = _make_app()
    async with app.run_test() as pilot:
        await _seed_item(app, pilot, 207)
        assert app._thread_url(207) == (
            "https://edstem.org/us/courses/98559/discussion/8100207")
        assert app._thread_url(999) is None  # not in queue


async def test_open_browser_opens_active_thread(monkeypatch):
    opened = []
    monkeypatch.setattr("ed_bot.cockpit.app.webbrowser.open", opened.append)
    app = _make_app()
    async with app.run_test() as pilot:
        await _seed_item(app, pilot, 207)
        app._active_thread = 207
        app.action_open_browser()
        assert opened == ["https://edstem.org/us/courses/98559/discussion/8100207"]


async def test_open_browser_no_active_thread_is_safe(monkeypatch):
    opened = []
    monkeypatch.setattr("ed_bot.cockpit.app.webbrowser.open", opened.append)
    app = _make_app()
    async with app.run_test() as pilot:
        app.action_open_browser()  # no active thread -> no crash, no open
        assert opened == []
