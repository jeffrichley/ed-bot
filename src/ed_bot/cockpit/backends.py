"""Live EdStem backends for the cockpit: fetch_events, post_fn, is_answered_fn.

Each wraps the synchronous ed_api / watch code in asyncio.to_thread so the
Textual event loop never blocks. The builders take an injected client/store so
they can be unit-tested with fakes; __main__ constructs the real ones.
"""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from ed_bot.cockpit.models import ActionResult, WatcherEvent


def build_is_answered_fn(*, client: Any) -> Callable[[int], Awaitable[bool]]:
    """Async is_answered check: True when the thread already has an accepted
    answer. Used by the loop's staleness guard before posting a NEW answer."""
    async def is_answered(thread_id: int) -> bool:
        detail = await asyncio.to_thread(client.threads.get, thread_id)
        return bool(detail.is_answered)
    return is_answered
