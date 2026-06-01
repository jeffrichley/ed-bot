"""Tests for the headless cockpit loop: routing, auto-draft, state."""
import asyncio
import pytest

from ed_bot.cockpit.models import (
    WatcherEvent, UserCommand, DraftPayload, QueueUpdate, DraftState,
)
from ed_bot.cockpit.loop import CockpitLoop


def _event(number=207, kind="new_thread"):
    return WatcherEvent(
        kind=kind, thread_id=8100000 + number, number=number,
        title=f"thread {number}", category="Project 1 | Martingale",
        url=f"https://edstem.org/x/{number}",
    )


def _payload(number=207):
    return DraftPayload(
        thread_id=8100000 + number, number=number, question="q",
        body="clean body", project="Project 1 - Martingale",
        confidence="HIGH",
    )


@pytest.mark.anyio
async def test_new_event_creates_queue_item_then_autodrafts():
    emitted = []

    async def fake_draft(*, number, **kw):
        return _payload(number)

    loop = CockpitLoop(
        cwd=".", course_id=98559,
        draft_fn=fake_draft, emit=lambda m: emitted.append(m),
    )
    await loop.handle(_event(207))

    item = loop.queue_item(207)
    assert item is not None
    assert item.draft_state == "ready"
    assert loop.draft(207).body == "clean body"
    assert any(isinstance(m, QueueUpdate) for m in emitted)


@pytest.mark.anyio
async def test_escalation_event_is_high_urgency():
    async def fake_draft(*, number, **kw):
        return _payload(number)
    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=fake_draft,
                       emit=lambda m: None)
    await loop.handle(_event(166, kind="escalation"))
    assert loop.queue_item(166).urgency == "high"


@pytest.mark.anyio
async def test_draft_failure_sets_failed_state():
    async def boom(*, number, **kw):
        raise RuntimeError("sdk down")
    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=boom,
                       emit=lambda m: None)
    await loop.handle(_event(207))
    assert loop.queue_item(207).draft_state == "failed"


@pytest.mark.anyio
async def test_open_command_returns_existing_draft():
    async def fake_draft(*, number, **kw):
        return _payload(number)
    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=fake_draft,
                       emit=lambda m: None)
    await loop.handle(_event(207))
    got = await loop.handle(UserCommand(intent="open", thread=207))
    assert got.number == 207
