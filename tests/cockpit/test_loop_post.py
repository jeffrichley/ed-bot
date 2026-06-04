"""Tests for approve/post flow with staleness re-check."""
import pytest

from ed_bot.cockpit.models import (
    WatcherEvent, UserCommand, DraftPayload, ActionResult, QueueItem, QueueUpdate,
    StatusUpdate,
)
from ed_bot.cockpit.loop import CockpitLoop


async def _ok_post(**kw):
    return ActionResult(thread_id=kw["thread_id"], ok=True, posted_id=1,
                        accepted=True)


async def _not_answered(thread_id):
    return False


def _event(number=207):
    return WatcherEvent(
        kind="new_thread", thread_id=8100000 + number, number=number,
        title=f"t{number}", category="Project 1 | Martingale",
        url=f"https://edstem.org/x/{number}",
    )


def _payload(number=207):
    return DraftPayload(thread_id=8100000 + number, number=number,
                        question="q", body="b", confidence="HIGH")


async def _draft(*, number, **kw):
    return _payload(number)


@pytest.mark.anyio
async def test_posting_removes_thread_from_rail():
    emitted = []
    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=_draft,
                       emit=emitted.append, post_fn=_ok_post,
                       is_answered_fn=_not_answered)
    await loop.handle(_event(207))  # creates the item + a single draft
    await loop.handle(UserCommand(intent="approve", thread=207))
    last = [e for e in emitted if isinstance(e, QueueUpdate)][-1]
    assert all(i.number != 207 for i in last.items)  # gone from the rail
    assert loop.targets_with_drafts(207) == []       # draft consumed


@pytest.mark.anyio
async def test_multidraft_thread_stays_until_all_posted():
    emitted = []
    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=None,
                       emit=emitted.append, post_fn=_ok_post,
                       is_answered_fn=_not_answered)
    loop._items[207] = QueueItem(
        thread_id=8100207, number=207, title="t",
        category="Project 1 | Martingale", kind="new_thread",
        draft_state="ready", status="needs_attention")
    for cid in (10, 20):
        loop._drafts[(207, cid)] = DraftPayload(
            thread_id=8100207, number=207, question="q", body=f"reply {cid}",
            post_kind="reply", target_comment_id=cid)
    await loop.handle(UserCommand(intent="approve", thread=207, target=10))
    after_first = [e for e in emitted if isinstance(e, QueueUpdate)][-1]
    assert any(i.number == 207 for i in after_first.items)  # 20 still pending
    await loop.handle(UserCommand(intent="approve", thread=207, target=20))
    after_second = [e for e in emitted if isinstance(e, QueueUpdate)][-1]
    assert all(i.number != 207 for i in after_second.items)  # now done -> gone


@pytest.mark.anyio
async def test_ok_without_posted_id_keeps_thread():
    """A backend reporting ok=True but returning no comment id means nothing
    actually landed: the draft must be kept and the thread must stay in the rail
    (the 'disappeared but didn't post' failure mode)."""
    emitted = []

    async def post_no_id(*, thread_id, number, body, post_kind, target_comment_id):
        return ActionResult(thread_id=thread_id, ok=True, posted_id=None)

    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=_draft,
                       emit=emitted.append, post_fn=post_no_id,
                       is_answered_fn=_not_answered)
    await loop.handle(_event(207))
    res = await loop.handle(UserCommand(intent="approve", thread=207))
    assert res.ok is True and res.posted_id is None
    assert loop.draft(207) is not None                       # draft kept
    assert loop.queue_item(207).status != "posted"
    last = [e for e in emitted if isinstance(e, QueueUpdate)][-1]
    assert any(i.number == 207 for i in last.items)          # still in the rail


@pytest.mark.anyio
async def test_failed_post_surfaces_status_and_keeps_thread():
    """A real post failure used to be silent. It must now surface a status line
    and leave the thread in the rail."""
    emitted = []

    async def post_fail(*, thread_id, number, body, post_kind, target_comment_id):
        return ActionResult(thread_id=thread_id, ok=False, message="boom")

    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=_draft,
                       emit=emitted.append, post_fn=post_fail,
                       is_answered_fn=_not_answered)
    await loop.handle(_event(207))
    res = await loop.handle(UserCommand(intent="approve", thread=207))
    assert res.ok is False
    lines = [e.line for e in emitted if isinstance(e, StatusUpdate)]
    assert any("NOT posted" in ln and "boom" in ln for ln in lines)
    assert loop.queue_item(207).status != "posted"


@pytest.mark.anyio
async def test_on_draft_ready_fires_when_draft_completes():
    fired = []
    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=_draft,
                       emit=lambda m: None, on_draft_ready=fired.append)
    await loop.handle(_event(207))
    assert fired == [207]


@pytest.mark.anyio
async def test_on_draft_ready_fires_on_demand_draft_one():
    fired = []

    async def reply_fn(*, number, cwd, course_id, target_comment_id):
        return DraftPayload(thread_id=8100207, number=number, question="q",
                            body="r", post_kind="reply",
                            target_comment_id=target_comment_id)

    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=None,
                       emit=lambda m: None, draft_reply_fn=reply_fn,
                       on_draft_ready=fired.append)
    loop._items[207] = QueueItem(
        thread_id=8100207, number=207, title="t",
        category="Project 1 | Martingale", kind="new_thread",
        draft_state="ready", status="needs_attention")
    out = await loop.draft_one(207, 55)
    assert out is not None
    assert fired == [207]


@pytest.mark.anyio
async def test_post_attempt_is_audit_logged_on_success():
    logged = []

    async def ok_post(*, thread_id, number, body, post_kind, target_comment_id):
        return ActionResult(thread_id=thread_id, ok=True, posted_id=555,
                            accepted=True)

    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=_draft,
                       emit=lambda m: None, post_fn=ok_post,
                       is_answered_fn=_not_answered, post_log_fn=logged.append)
    await loop.handle(_event(207))
    await loop.handle(UserCommand(intent="approve", thread=207))
    assert len(logged) == 1
    e = logged[0]
    assert e["number"] == 207
    assert e["thread_id"] == 8100207        # the authoritative global id
    assert e["post_kind"] == "answer" and e["is_answer"] is True
    assert e["ok"] is True and e["posted_id"] == 555 and e["accepted"] is True
    assert e["body"] == "b"


@pytest.mark.anyio
async def test_post_attempt_is_audit_logged_on_failure():
    logged = []

    async def post_fail(*, thread_id, number, body, post_kind, target_comment_id):
        return ActionResult(thread_id=thread_id, ok=False, message="boom")

    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=_draft,
                       emit=lambda m: None, post_fn=post_fail,
                       is_answered_fn=_not_answered, post_log_fn=logged.append)
    await loop.handle(_event(207))
    await loop.handle(UserCommand(intent="approve", thread=207))
    assert len(logged) == 1
    assert logged[0]["ok"] is False and logged[0]["message"] == "boom"
    assert logged[0]["posted_id"] is None


@pytest.mark.anyio
async def test_approve_posts_and_marks_posted():
    posted = {}

    async def fake_post(*, thread_id, number, body, post_kind, target_comment_id):
        posted["called"] = number
        posted["thread_id"] = thread_id
        return ActionResult(thread_id=thread_id, ok=True,
                            posted_id=999, accepted=True, message="ok")

    async def fresh_is_answered(thread_id):
        return False  # still open

    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=_draft,
                       emit=lambda m: None, post_fn=fake_post,
                       is_answered_fn=fresh_is_answered)
    await loop.handle(_event(207))
    res = await loop.handle(UserCommand(intent="approve", thread=207))

    assert isinstance(res, ActionResult)
    assert res.ok and res.accepted
    assert posted["called"] == 207
    assert posted["thread_id"] == 8100207
    assert loop.queue_item(207).status == "posted"


@pytest.mark.anyio
async def test_approve_skips_post_when_already_answered():
    async def fake_post(*, thread_id, number, body, post_kind, target_comment_id):
        raise AssertionError("must not post a stale thread")

    async def stale_is_answered(thread_id):
        return True  # staff already answered

    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=_draft,
                       emit=lambda m: None, post_fn=fake_post,
                       is_answered_fn=stale_is_answered)
    await loop.handle(_event(207))
    res = await loop.handle(UserCommand(intent="approve", thread=207))

    assert res.ok is False
    assert "already answered" in res.message.lower()
    assert loop.queue_item(207).status != "posted"


@pytest.mark.anyio
async def test_reply_not_blocked_by_is_answered():
    """A follow-up reply legitimately targets an already-answered thread, so the
    staleness guard must not skip it."""
    posts = []

    async def post_fn(*, thread_id, number, body, post_kind, target_comment_id):
        posts.append((thread_id, post_kind, target_comment_id))
        return ActionResult(thread_id=thread_id, ok=True, posted_id=1)

    async def is_answered_fn(thread_id):
        return True  # thread already has an accepted answer

    loop = CockpitLoop(cwd=".", course_id=1, draft_fn=None, emit=lambda x: None,
                       post_fn=post_fn, is_answered_fn=is_answered_fn)
    loop._drafts[(207, None)] = DraftPayload(
        thread_id=8100207, number=207, question="q", body="reply body",
        post_kind="reply", target_comment_id=909)

    res = await loop.handle(UserCommand(intent="approve", thread=207))
    assert res.ok is True
    assert posts == [(8100207, "reply", 909)]


@pytest.mark.anyio
async def test_answer_forwards_thread_id_to_post_fn():
    seen = {}

    async def post_fn(*, thread_id, number, body, post_kind, target_comment_id):
        seen["thread_id"] = thread_id
        return ActionResult(thread_id=thread_id, ok=True, posted_id=1)

    async def is_answered_fn(thread_id):
        seen["checked"] = thread_id
        return False

    loop = CockpitLoop(cwd=".", course_id=1, draft_fn=None, emit=lambda x: None,
                       post_fn=post_fn, is_answered_fn=is_answered_fn)
    loop._drafts[(207, None)] = DraftPayload(
        thread_id=8100207, number=207, question="q", body="answer body",
        post_kind="answer")

    await loop.handle(UserCommand(intent="approve", thread=207))
    assert seen["thread_id"] == 8100207
    assert seen["checked"] == 8100207
