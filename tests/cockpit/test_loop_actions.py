"""reject / flag / skip queue actions."""
import pytest

from ed_bot.cockpit.loop import CockpitLoop
from ed_bot.cockpit.models import (
    WatcherEvent, UserCommand, QueueUpdate, DraftPayload,
)

pytestmark = pytest.mark.anyio


def _loop():
    emitted = []
    loop = CockpitLoop(cwd=".", course_id=1, draft_fn=None, emit=emitted.append)
    return loop, emitted


def _seed(loop, number=207):
    from ed_bot.cockpit.models import QueueItem
    loop._items[number] = QueueItem(
        thread_id=8100000 + number, number=number, title="t",
        category="Project 1 | Martingale", kind="new_thread",
        draft_state="ready", status="needs_attention")


async def test_reject_dismisses_and_drops_from_rail():
    loop, emitted = _loop()
    _seed(loop, 207)
    await loop.handle(UserCommand(intent="reject", thread=207))
    assert loop.queue_item(207).status == "dismissed"
    # The last queue update no longer contains #207.
    last = [e for e in emitted if isinstance(e, QueueUpdate)][-1]
    assert all(i.number != 207 for i in last.items)


async def test_flag_marks_flagged_but_keeps_in_rail():
    loop, emitted = _loop()
    _seed(loop, 207)
    await loop.handle(UserCommand(intent="flag", thread=207))
    assert loop.queue_item(207).draft_state == "flagged"
    last = [e for e in emitted if isinstance(e, QueueUpdate)][-1]
    assert any(i.number == 207 for i in last.items)  # still visible


async def test_skip_leaves_thread_untouched():
    loop, emitted = _loop()
    _seed(loop, 207)
    await loop.handle(UserCommand(intent="skip", thread=207))
    assert loop.queue_item(207).status == "needs_attention"
    assert loop.queue_item(207).draft_state == "ready"
