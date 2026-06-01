"""Tests that the app composes Layout A and routes loop emissions to widgets."""
import pytest

from ed_bot.cockpit.app import CockpitApp
from ed_bot.cockpit.widgets import QueueRail, DraftViewer, StatusBar
from ed_bot.cockpit.models import WatcherEvent, DraftPayload


def _make_app():
    async def draft_fn(*, number, **kw):
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question="q", body="clean body", confidence="HIGH")

    return CockpitApp(cwd=".", course_id=98559, draft_fn=draft_fn,
                      post_fn=None, is_answered_fn=None,
                      fetch_events=None)


@pytest.mark.anyio
async def test_app_mounts_core_widgets():
    app = _make_app()
    async with app.run_test() as pilot:
        assert app.query_one(QueueRail)
        assert app.query_one(DraftViewer)
        assert app.query_one(StatusBar)


@pytest.mark.anyio
async def test_event_autodrafts_and_queue_rail_updates():
    app = _make_app()
    async with app.run_test() as pilot:
        await app.inject_event(WatcherEvent(
            kind="new_thread", thread_id=8100207, number=207,
            title="Figure 1 graph", category="Project 1 | Martingale", url="u"))
        await pilot.pause()
        rail = app.query_one(QueueRail)
        assert "207" in str(rail.content)
