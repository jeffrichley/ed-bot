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


async def test_watch_loop_calls_on_poll_each_cycle():
    import asyncio
    from ed_bot.cockpit.watcher import watch_loop

    ticks = []
    stop = asyncio.Event()
    polls = [0]

    async def fetch_events(cid):
        polls[0] += 1
        if polls[0] >= 2:
            stop.set()
        return []

    await watch_loop(course_id=1, queue=asyncio.Queue(), fetch_events=fetch_events,
                     interval_seconds=0.01, stop=stop, on_poll=lambda: ticks.append(1))
    assert len(ticks) >= 2  # heartbeat fired each poll


async def test_app_shows_watching_heartbeat():
    from ed_bot.cockpit.app import CockpitApp

    async def fetch_events(cid):
        return []

    async def draft_fn(*, number, cwd, course_id):  # pragma: no cover - unused
        raise AssertionError

    app = CockpitApp(cwd=".", course_id=1, draft_fn=draft_fn,
                     fetch_events=fetch_events, watch_interval=0.05)
    async with app.run_test() as pilot:
        for _ in range(20):
            await pilot.pause()
            if "last checked" in (app.sub_title or ""):
                break
        assert "watching" in app.sub_title and "last checked" in app.sub_title


async def test_no_watch_says_not_watching():
    from ed_bot.cockpit.app import CockpitApp

    async def draft_fn(*, number, cwd, course_id):  # pragma: no cover
        raise AssertionError

    app = CockpitApp(cwd=".", course_id=1, draft_fn=draft_fn, fetch_events=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert "not watching" in app.sub_title
