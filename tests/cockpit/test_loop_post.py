"""Tests for approve/post flow with staleness re-check."""
import pytest

from ed_bot.cockpit.models import WatcherEvent, UserCommand, DraftPayload, ActionResult
from ed_bot.cockpit.loop import CockpitLoop


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
async def test_approve_posts_and_marks_posted():
    posted = {}

    async def fake_post(*, number, body, post_kind, target_comment_id):
        posted["called"] = number
        return ActionResult(thread_id=8100000 + number, ok=True,
                            posted_id=999, accepted=True, message="ok")

    async def fresh_is_answered(number):
        return False  # still open

    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=_draft,
                       emit=lambda m: None, post_fn=fake_post,
                       is_answered_fn=fresh_is_answered)
    await loop.handle(_event(207))
    res = await loop.handle(UserCommand(intent="approve", thread=207))

    assert isinstance(res, ActionResult)
    assert res.ok and res.accepted
    assert posted["called"] == 207
    assert loop.queue_item(207).status == "posted"


@pytest.mark.anyio
async def test_approve_skips_post_when_already_answered():
    async def fake_post(*, number, body, post_kind, target_comment_id):
        raise AssertionError("must not post a stale thread")

    async def stale_is_answered(number):
        return True  # staff already answered

    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=_draft,
                       emit=lambda m: None, post_fn=fake_post,
                       is_answered_fn=stale_is_answered)
    await loop.handle(_event(207))
    res = await loop.handle(UserCommand(intent="approve", thread=207))

    assert res.ok is False
    assert "already answered" in res.message.lower()
    assert loop.queue_item(207).status != "posted"
