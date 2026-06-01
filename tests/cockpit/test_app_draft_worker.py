"""The draft path must run as a background worker, not block the message pump.

Regression for the live freeze: seeding events awaited the auto-draft inline on
Textual's message pump, freezing the UI (no render, no input) for the duration
of the live SDK call. The fix: draft_event runs loop.handle as a @work worker.
"""
import asyncio
import pytest

from ed_bot.cockpit.app import CockpitApp
from ed_bot.cockpit.widgets import QueueRail
from ed_bot.cockpit.models import WatcherEvent, DraftPayload


def _event(number):
    return WatcherEvent(kind="new_thread", thread_id=8100000 + number,
                        number=number, title=f"t{number}",
                        category="Project 1 | Martingale", url="u")


@pytest.mark.anyio
async def test_draft_event_is_nonblocking_and_populates_queue():
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_draft(*, number, **kw):
        started.set()
        await release.wait()  # hold the draft open
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question="q", body=f"body {number}", confidence="HIGH")

    app = CockpitApp(cwd=".", course_id=98559, draft_fn=slow_draft,
                     post_fn=None, is_answered_fn=None, fetch_events=None)
    async with app.run_test() as pilot:
        # Fire as a worker (no await) — must return immediately.
        app.draft_event(_event(207))
        # Pump runs; the queue row should appear while the draft is still held.
        for _ in range(20):
            await pilot.pause()
            if started.is_set():
                break
        rail = app.query_one(QueueRail)
        labels = [str(rail.get_option_at_index(i).prompt)
                  for i in range(rail.option_count)]
        # The row is present and shows it's drafting, even though the draft
        # has NOT returned (release not set) — proving the pump wasn't blocked.
        assert any("207" in l for l in labels)
        assert any("drafting" in l for l in labels)
        # Now let the draft finish and confirm it reaches ready.
        release.set()
        for _ in range(20):
            await pilot.pause()
            if app.loop.queue_item(207) and app.loop.queue_item(207).draft_state == "ready":
                break
        assert app.loop.queue_item(207).draft_state == "ready"
