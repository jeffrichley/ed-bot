"""Selecting a queue item opens its draft in the viewer."""
import pytest

from ed_bot.cockpit.app import CockpitApp
from ed_bot.cockpit.widgets import QueueRail, DraftViewer
from ed_bot.cockpit.models import WatcherEvent, DraftPayload


def _make_app():
    async def draft_fn(*, number, **kw):
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question=f"q{number}", body=f"body {number}",
                            confidence="HIGH")
    return CockpitApp(cwd=".", course_id=98559, draft_fn=draft_fn,
                      post_fn=None, is_answered_fn=None, fetch_events=None)


@pytest.mark.anyio
async def test_selecting_queue_item_opens_its_draft():
    app = _make_app()
    async with app.run_test() as pilot:
        await app.inject_event(WatcherEvent(
            kind="new_thread", thread_id=8100207, number=207, title="t207",
            category="Project 1 | Martingale", url="u"))
        await app.inject_event(WatcherEvent(
            kind="new_thread", thread_id=8100225, number=225, title="t225",
            category="Project 1 | Martingale", url="u"))
        await pilot.pause()
        rail = app.query_one(QueueRail)
        rail.focus()
        rail.highlighted = 1
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        draft_text = str(app.query_one(DraftViewer).content)
        assert "body 225" in draft_text
