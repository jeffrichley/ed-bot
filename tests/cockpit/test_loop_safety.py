"""Production-safety guards: never post a placeholder; route edit to chat-edit;
draft-on-demand."""
import pytest

from ed_bot.cockpit.loop import CockpitLoop
from ed_bot.cockpit.models import UserCommand, DraftPayload, ActionResult

pytestmark = pytest.mark.anyio


def _draft(body, target=None):
    return DraftPayload(thread_id=8100207, number=207, question="q", body=body,
                        post_kind="answer" if target is None else "reply",
                        target_comment_id=target)


async def _loop_with_post():
    posts = []

    async def post_fn(**kw):
        posts.append(kw)
        return ActionResult(thread_id=kw["thread_id"], ok=True, posted_id=1)

    async def is_answered_fn(thread_id):
        return False

    loop = CockpitLoop(cwd=".", course_id=1, draft_fn=None, emit=lambda e: None,
                       post_fn=post_fn, is_answered_fn=is_answered_fn)
    return loop, posts


async def test_approve_refuses_needs_human_body():
    loop, posts = await _loop_with_post()
    loop._drafts[(207, None)] = _draft("NEEDS HUMAN — already resolved by staff")
    res = await loop.handle(UserCommand(intent="approve", thread=207))
    assert res.ok is False
    assert posts == []  # post_fn never called


async def test_approve_refuses_empty_body():
    loop, posts = await _loop_with_post()
    loop._drafts[(207, None)] = _draft("   \n  ")
    res = await loop.handle(UserCommand(intent="approve", thread=207))
    assert res.ok is False
    assert posts == []


async def test_approve_posts_a_real_body():
    loop, posts = await _loop_with_post()
    loop._drafts[(207, None)] = _draft("Here is a real answer.")
    res = await loop.handle(UserCommand(intent="approve", thread=207))
    assert res.ok is True
    assert len(posts) == 1


async def test_edit_intent_routes_to_chat_edit():
    edited = []

    async def chat_edit_fn(**kw):
        edited.append(kw)
        return {"reply": "done", "revised_body": "SHORTER"}

    loop = CockpitLoop(cwd=".", course_id=1, draft_fn=None, emit=lambda e: None,
                       chat_edit_fn=chat_edit_fn, rescan_fn=lambda b, p: [])
    loop._drafts[(207, None)] = _draft("a long answer")
    await loop.handle(UserCommand(intent="edit", thread=207, text="shorten it"))
    assert edited  # the edit-aware path ran
    assert loop.draft(207).body == "SHORTER"


async def test_draft_one_drafts_on_demand():
    async def draft_reply_fn(*, number, cwd, course_id, target_comment_id):
        return DraftPayload(thread_id=8100207, number=number, question="q",
                            body=f"on-demand reply to {target_comment_id}",
                            post_kind="reply", target_comment_id=target_comment_id)

    loop = CockpitLoop(cwd=".", course_id=1, draft_fn=None, emit=lambda e: None,
                       draft_reply_fn=draft_reply_fn)
    assert loop.draft(207, 55) is None
    payload = await loop.draft_one(207, 55)
    assert payload.body == "on-demand reply to 55"
    assert loop.draft(207, 55).body == "on-demand reply to 55"
