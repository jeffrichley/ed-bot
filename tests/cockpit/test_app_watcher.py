import pytest

pytestmark = pytest.mark.anyio


async def test_app_watcher_drafts_polled_event():
    """With a fetch_events that yields one event, the app's watcher creates a
    queue item and drafts it."""
    from ed_bot.cockpit.app import CockpitApp
    from ed_bot.cockpit.models import DraftPayload, WatcherEvent

    async def fetch_events(cid):
        return [WatcherEvent(kind="new_thread", thread_id=900, number=42,
                             title="Bollinger help",
                             category="Project 6 | Indicators",
                             url="https://edstem.org/x")]

    async def draft_fn(*, number, cwd, course_id):
        return DraftPayload(thread_id=900, number=number, question="q",
                            body="drafted body", post_kind="answer")

    app = CockpitApp(cwd=".", course_id=1, draft_fn=draft_fn,
                     fetch_events=fetch_events, watch_interval=0.05)
    async with app.run_test() as pilot:
        # Let the producer poll once and the consumer draft it.
        for _ in range(20):
            await pilot.pause()
            if app.loop.queue_item(42) is not None and app.loop.draft(42) is not None:
                break
        assert app.loop.queue_item(42) is not None
        assert app.loop.draft(42).body == "drafted body"
