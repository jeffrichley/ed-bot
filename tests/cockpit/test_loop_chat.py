"""Tests for the loop's chat handling: freeform -> ed-bot reply, check_forum -> summary."""
import pytest

from ed_bot.cockpit.models import (
    WatcherEvent, UserCommand, DraftPayload, ChatMessage, StatusUpdate,
)
from ed_bot.cockpit.loop import CockpitLoop


async def _draft(*, number, **kw):
    return DraftPayload(thread_id=8100000 + number, number=number,
                        question="q", body="b", confidence="HIGH")


def _event(number=207):
    return WatcherEvent(kind="new_thread", thread_id=8100000 + number,
                        number=number, title=f"t{number}",
                        category="Project 1 | Martingale", url="u")


@pytest.mark.anyio
async def test_freeform_emits_ed_bot_chat_message():
    emitted = []

    async def chat_fn(*, text, cwd, course_id):
        return f"echo: {text}"

    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=_draft,
                       emit=lambda m: emitted.append(m), chat_fn=chat_fn)
    await loop.handle(UserCommand(intent="freeform", text="hello there"))

    chats = [m for m in emitted if isinstance(m, ChatMessage)]
    assert any(c.role == "ed-bot" and "echo: hello there" in c.text for c in chats)


@pytest.mark.anyio
async def test_freeform_shows_thinking_then_clears():
    emitted = []

    async def chat_fn(*, text, cwd, course_id):
        return "the reply"

    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=_draft,
                       emit=lambda m: emitted.append(m), chat_fn=chat_fn)
    await loop.handle(UserCommand(intent="freeform", text="hi"))

    statuses = [m.line for m in emitted if isinstance(m, StatusUpdate)]
    # A "thinking" status fires before the reply, and is cleared afterward.
    assert any("thinking" in s.lower() for s in statuses)
    # The thinking status comes before the ed-bot reply in emission order.
    thinking_idx = next(i for i, m in enumerate(emitted)
                        if isinstance(m, StatusUpdate) and "thinking" in m.line.lower())
    reply_idx = next(i for i, m in enumerate(emitted)
                     if isinstance(m, ChatMessage) and m.role == "ed-bot")
    assert thinking_idx < reply_idx
    # Final status is back to a non-thinking line.
    assert statuses and "thinking" not in statuses[-1].lower()


@pytest.mark.anyio
async def test_check_forum_summarizes_queue():
    emitted = []
    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=_draft,
                       emit=lambda m: emitted.append(m))
    await loop.handle(_event(207))
    emitted.clear()
    await loop.handle(UserCommand(intent="check_forum"))

    chats = [m for m in emitted if isinstance(m, ChatMessage)]
    assert chats and chats[-1].role == "ed-bot"
    assert "207" in chats[-1].text


@pytest.mark.anyio
async def test_check_forum_empty_queue_says_empty():
    emitted = []
    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=_draft,
                       emit=lambda m: emitted.append(m))
    await loop.handle(UserCommand(intent="check_forum"))
    chats = [m for m in emitted if isinstance(m, ChatMessage)]
    assert chats and "empty" in chats[-1].text.lower()
