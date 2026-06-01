"""Tests for the async watcher task."""
import asyncio
import pytest

from ed_bot.cockpit.models import WatcherEvent
from ed_bot.cockpit.watcher import poll_once


@pytest.mark.anyio
async def test_poll_once_puts_events_on_queue():
    q: asyncio.Queue = asyncio.Queue()

    async def fake_fetch_events(course_id):
        return [
            WatcherEvent(kind="new_thread", thread_id=1, number=207,
                         title="t", category="Project 1 | Martingale",
                         url="u"),
        ]

    await poll_once(course_id=98559, queue=q, fetch_events=fake_fetch_events)
    assert q.qsize() == 1
    ev = await q.get()
    assert ev.number == 207


@pytest.mark.anyio
async def test_poll_once_tolerates_fetch_failure():
    q: asyncio.Queue = asyncio.Queue()

    async def boom(course_id):
        raise RuntimeError("api down")

    # Must not raise; a transient poll failure should be swallowed.
    await poll_once(course_id=98559, queue=q, fetch_events=boom)
    assert q.qsize() == 0
