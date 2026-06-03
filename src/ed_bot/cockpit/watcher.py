"""The async watcher task: poll EdStem, put WatcherEvents on the queue.

The forum fetch is injected. The real wiring wraps the synchronous ed-api
client with ``asyncio.to_thread`` so the poll never blocks the event loop."""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from ed_bot.cockpit.models import WatcherEvent

log = logging.getLogger(__name__)

FetchEvents = Callable[[int], Awaitable[list[WatcherEvent]]]


async def poll_once(*, course_id: int, queue: "asyncio.Queue",
                    fetch_events: FetchEvents) -> None:
    """One poll cycle: fetch actionable events and enqueue them. Swallows
    transient fetch failures so the watcher loop survives."""
    try:
        events = await fetch_events(course_id)
    except Exception as e:  # noqa: BLE001 - one bad poll must not kill the loop
        log.warning("watcher poll failed: %s", e)
        return
    for ev in events:
        await queue.put(ev)


async def watch_loop(*, course_id: int, queue: "asyncio.Queue",
                     fetch_events: FetchEvents, interval_seconds: float,
                     stop: "asyncio.Event",
                     on_poll: "Callable[[], None] | None" = None) -> None:
    """Poll on an interval until ``stop`` is set. ``on_poll`` (if given) is
    called after each poll cycle, so the UI can show a 'last checked' heartbeat."""
    while not stop.is_set():
        await poll_once(course_id=course_id, queue=queue,
                        fetch_events=fetch_events)
        if on_poll is not None:
            on_poll()
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass
