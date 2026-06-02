"""Focus modes (chat vs. action) + open-in-browser action."""
import pytest
from textual.widgets import Input

from ed_bot.cockpit.app import CockpitApp
from ed_bot.cockpit.widgets import QueueRail
from ed_bot.cockpit.models import WatcherEvent, DraftPayload, ActionResult

pytestmark = pytest.mark.anyio


def _make_app(post_fn=None, is_answered_fn=None):
    async def draft_fn(*, number, **kw):
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question=f"q{number}", body=f"body {number}",
                            confidence="HIGH")
    return CockpitApp(cwd=".", course_id=98559, draft_fn=draft_fn,
                      post_fn=post_fn, is_answered_fn=is_answered_fn,
                      fetch_events=None)


async def _seed_item(app, pilot, number):
    await app.inject_event(WatcherEvent(
        kind="new_thread", thread_id=8100000 + number, number=number,
        title=f"t{number}", category="Project 1 | Martingale", url="u"))
    await pilot.pause()


async def test_selecting_thread_keeps_action_focus():
    """After opening a thread from the queue, focus stays on the queue so the
    action hotkeys (a/e/r/f/s/o) act on it instead of typing into chat."""
    app = _make_app()
    async with app.run_test() as pilot:
        await _seed_item(app, pilot, 207)
        rail = app.query_one(QueueRail)
        rail.focus()
        await pilot.pause()
        rail.highlighted = 0
        await pilot.press("enter")
        await pilot.pause()
        assert app.focused is rail  # NOT the chat input


async def test_press_a_in_action_mode_approves(monkeypatch):
    """The user's case: select a thread, press 'a' -> it approves, not types."""
    posted = []

    async def post_fn(*, thread_id, number, body, post_kind, target_comment_id):
        posted.append((thread_id, number))
        return ActionResult(thread_id=thread_id, ok=True, posted_id=1)

    async def is_answered_fn(thread_id):
        return False

    app = _make_app(post_fn=post_fn, is_answered_fn=is_answered_fn)
    async with app.run_test() as pilot:
        await _seed_item(app, pilot, 207)
        rail = app.query_one(QueueRail)
        rail.focus()
        await pilot.pause()
        rail.highlighted = 0
        await pilot.press("enter")   # open the draft (active thread = 207)
        await pilot.pause()
        await pilot.press("a")       # approve via hotkey
        await pilot.pause()
        await pilot.pause()
        assert posted == [(8100207, 207)]


async def test_escape_toggles_between_chat_and_queue():
    app = _make_app()
    async with app.run_test() as pilot:
        await _seed_item(app, pilot, 207)
        chat = app.query_one("#chat", Input)
        chat.focus()
        await pilot.pause()
        assert app.focused is chat
        await pilot.press("escape")          # chat -> actions
        await pilot.pause()
        assert app.focused is app.query_one(QueueRail)
        await pilot.press("escape")          # actions -> chat
        await pilot.pause()
        assert app.focused is chat


async def test_thread_url_uses_global_thread_id_and_course():
    app = _make_app()
    async with app.run_test() as pilot:
        await _seed_item(app, pilot, 207)
        assert app._thread_url(207) == (
            "https://edstem.org/us/courses/98559/discussion/8100207")
        assert app._thread_url(999) is None


async def test_open_browser_opens_active_thread(monkeypatch):
    opened = []
    monkeypatch.setattr("ed_bot.cockpit.app.webbrowser.open", opened.append)
    app = _make_app()
    async with app.run_test() as pilot:
        await _seed_item(app, pilot, 207)
        app._active_thread = 207
        app.action_open_browser()
        assert opened == ["https://edstem.org/us/courses/98559/discussion/8100207"]


async def test_open_browser_uses_highlight_while_drafting(monkeypatch):
    """Open the highlighted thread even before its draft is opened (i.e. while
    it is still drafting). Needs only the queued thread's global id."""
    opened = []
    monkeypatch.setattr("ed_bot.cockpit.app.webbrowser.open", opened.append)
    app = _make_app()
    async with app.run_test() as pilot:
        await _seed_item(app, pilot, 207)
        rail = app.query_one(QueueRail)
        rail.focus()
        await pilot.pause()
        rail.highlighted = 0
        assert app._active_thread is None  # never opened the draft
        app.action_open_browser()
        assert opened == ["https://edstem.org/us/courses/98559/discussion/8100207"]


async def test_open_browser_no_active_thread_is_safe(monkeypatch):
    opened = []
    monkeypatch.setattr("ed_bot.cockpit.app.webbrowser.open", opened.append)
    app = _make_app()
    async with app.run_test() as pilot:
        app.action_open_browser()
        assert opened == []
