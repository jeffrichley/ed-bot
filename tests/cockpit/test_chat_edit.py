"""Chat can revise the active draft, and the viewer refreshes."""
import pytest

from ed_bot.cockpit import agent
from textual.widgets import TextArea

from ed_bot.cockpit.app import CockpitApp
from ed_bot.cockpit.loop import CockpitLoop
from ed_bot.cockpit.models import (
    UserCommand, DraftPayload, ChatMessage, WatcherEvent,
)

pytestmark = pytest.mark.anyio


def _draft(number=207, body="OLD BODY", project=None):
    return DraftPayload(thread_id=8100000 + number, number=number, question="q",
                        body=body, original_content="student: help me\nstaff: ok",
                        project=project)


# --- loop edit path ---

async def test_chat_edits_active_draft_and_emits_updated():
    emitted = []

    async def chat_edit_fn(*, text, cwd, course_id, history, thread_content,
                           current_body):
        assert current_body == "OLD BODY"           # got the current draft
        assert "student: help me" in thread_content  # got the thread text
        return {"reply": "Reworded it.", "revised_body": "NEW BODY"}

    loop = CockpitLoop(cwd=".", course_id=1, draft_fn=None, emit=emitted.append,
                       chat_edit_fn=chat_edit_fn)
    loop._drafts[(207, None)] = _draft()
    await loop.handle(UserCommand(intent="freeform", thread=207, text="reword it"))

    assert loop.draft(207).body == "NEW BODY"
    drafts = [e for e in emitted if isinstance(e, DraftPayload)]
    bot = [e for e in emitted if isinstance(e, ChatMessage) and e.role == "ed-bot"]
    assert drafts and drafts[-1].body == "NEW BODY"   # viewer-refresh emission
    assert bot and bot[-1].text == "Reworded it."


async def test_chat_question_leaves_draft_unchanged():
    emitted = []

    async def chat_edit_fn(*, text, cwd, course_id, history, thread_content,
                           current_body):
        return {"reply": "Looks fine to me.", "revised_body": None}

    loop = CockpitLoop(cwd=".", course_id=1, draft_fn=None, emit=emitted.append,
                       chat_edit_fn=chat_edit_fn)
    loop._drafts[(207, None)] = _draft()
    await loop.handle(UserCommand(intent="freeform", thread=207, text="is this ok?"))

    assert loop.draft(207).body == "OLD BODY"
    assert not [e for e in emitted if isinstance(e, DraftPayload)]


async def test_freeform_without_active_draft_uses_plain_chat():
    async def chat_fn(*, text, cwd, course_id, history):
        return "plain reply"

    async def chat_edit_fn(**kw):  # should not be called
        raise AssertionError("edit path used without an active draft")

    loop = CockpitLoop(cwd=".", course_id=1, draft_fn=None, emit=lambda e: None,
                       chat_fn=chat_fn, chat_edit_fn=chat_edit_fn)
    # No draft for the thread -> plain chat.
    await loop.handle(UserCommand(intent="freeform", thread=None, text="hi"))


async def test_edit_rescans_guardrails_on_revised_body():
    async def chat_edit_fn(**kw):
        return {"reply": "done", "revised_body": "NEW BODY"}

    loop = CockpitLoop(cwd=".", course_id=1, draft_fn=None, emit=lambda e: None,
                       chat_edit_fn=chat_edit_fn,
                       rescan_fn=lambda body, project: ["possible leak 18/38"])
    loop._drafts[(207, None)] = _draft(project="Project 1 - Martingale")
    await loop.handle(UserCommand(intent="freeform", thread=207, text="reword"))
    assert loop.draft(207).guardrail_warnings == ["possible leak 18/38"]


# --- agent structured edit call ---

async def test_chat_edit_prompt_carries_thread_and_draft():
    captured = {}

    async def fake_sdk_query(*, prompt, schema, cwd):
        captured["prompt"] = prompt
        captured["schema"] = schema
        return {"reply": "ok", "revised_body": "NEW"}

    out = await agent.chat_edit(
        text="make it shorter", cwd=".", course_id=99,
        thread_content="THREAD TEXT HERE", current_body="CURRENT DRAFT",
        history=[("you", "hi"), ("ed-bot", "hello")], sdk_query=fake_sdk_query)

    assert out == {"reply": "ok", "revised_body": "NEW"}
    assert "THREAD TEXT HERE" in captured["prompt"]
    assert "CURRENT DRAFT" in captured["prompt"]
    assert "make it shorter" in captured["prompt"]
    assert "revised_body" in captured["schema"]["properties"]


# --- app refreshes the viewer on an edited draft ---

async def test_viewer_refreshes_when_active_draft_is_edited():
    async def draft_fn(*, number, **kw):
        return _draft(number=number, body=f"body {number}")
    app = CockpitApp(cwd=".", course_id=98559, draft_fn=draft_fn)
    async with app.run_test() as pilot:
        await app.inject_event(WatcherEvent(
            kind="new_thread", thread_id=8100207, number=207, title="t",
            category="Project 1 | Martingale", url="u"))
        await pilot.pause()
        app._active_thread = 207
        app._emit(_draft(number=207, body="EDITED IN CHAT"))
        await pilot.pause()
        assert "EDITED IN CHAT" in app.query_one("#draft", TextArea).text
