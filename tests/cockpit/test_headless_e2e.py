"""End-to-end headless wiring: watcher queue -> loop -> auto-draft -> approve."""
import asyncio
import pytest

from ed_bot.cockpit.models import WatcherEvent, UserCommand, DraftPayload, ActionResult
from ed_bot.cockpit.loop import CockpitLoop
from ed_bot.cockpit.watcher import poll_once


@pytest.mark.anyio
async def test_event_to_post_round_trip():
    q: asyncio.Queue = asyncio.Queue()

    async def fetch_events(course_id):
        return [WatcherEvent(kind="new_thread", thread_id=8100207, number=207,
                             title="Figure 1 graph",
                             category="Project 1 | Martingale", url="u")]

    async def draft_fn(*, number, **kw):
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question="q", body="clean answer", confidence="HIGH")

    async def post_fn(*, number, body, post_kind, target_comment_id):
        return ActionResult(thread_id=8100000 + number, ok=True, posted_id=42,
                            accepted=True, message="ok")

    async def is_answered_fn(number):
        return False

    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=draft_fn,
                       emit=lambda m: None, post_fn=post_fn,
                       is_answered_fn=is_answered_fn)

    # 1. Watcher polls -> event on queue.
    await poll_once(course_id=98559, queue=q, fetch_events=fetch_events)
    # 2. Consumer drains the queue and routes to the loop.
    ev = await q.get()
    await loop.handle(ev)
    # 3. Auto-draft completed.
    assert loop.queue_item(207).draft_state == "ready"
    # 4. Human approves -> posts.
    res = await loop.handle(UserCommand(intent="approve", thread=207))
    assert res.ok and res.accepted
    assert loop.queue_item(207).status == "posted"
