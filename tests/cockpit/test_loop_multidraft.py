"""Auto-drafting a reply for each open question (per-comment drafting)."""
import pytest

from ed_bot.cockpit.loop import CockpitLoop
from ed_bot.cockpit.thread_tree import CommentNode
from ed_bot.cockpit.models import WatcherEvent, DraftPayload

pytestmark = pytest.mark.anyio


def _two_open_questions():
    return CommentNode(
        comment_id=None, author="Jane", role="student", is_staff=False, text="OP",
        children=[
            CommentNode(comment_id=10, author="Bob", role="student",
                        is_staff=False, text="Q1", children=[], needs_reply=True),
            CommentNode(comment_id=20, author="Amy", role="student",
                        is_staff=False, text="Q2", children=[], needs_reply=True),
        ])


async def _run(op):
    drafted_targets = []

    async def draft_reply_fn(*, number, cwd, course_id, target_comment_id):
        drafted_targets.append(target_comment_id)
        return DraftPayload(thread_id=8100207, number=number, question="q",
                            body=f"reply to {target_comment_id}",
                            post_kind="reply", target_comment_id=target_comment_id)

    async def fetch_tree_fn(course_id, number):
        return op

    loop = CockpitLoop(cwd=".", course_id=1, draft_fn=None, emit=lambda e: None,
                       fetch_tree_fn=fetch_tree_fn, draft_reply_fn=draft_reply_fn)
    await loop.handle(WatcherEvent(
        kind="new_thread", thread_id=8100207, number=207, title="t",
        category="Project 1 | Martingale", url="u"))
    return loop, drafted_targets


async def test_autodrafts_a_reply_per_open_question():
    loop, drafted = await _run(_two_open_questions())
    # Both open questions got their own draft, keyed by comment.
    assert set(drafted) == {10, 20}
    assert loop.draft(207, 10).body == "reply to 10"
    assert loop.draft(207, 20).body == "reply to 20"
    assert sorted(t for t in loop.targets_with_drafts(207)) == [10, 20]
    assert loop.queue_item(207).draft_state == "ready"


async def test_no_open_questions_drafts_nothing():
    handled = CommentNode(comment_id=None, author="Jane", role="student",
                          is_staff=False, text="OP", children=[
        CommentNode(comment_id=10, author="Steven", role="staff", is_staff=True,
                    text="answer", children=[], needs_reply=False)])
    loop, drafted = await _run(handled)
    assert drafted == []
    assert loop.targets_with_drafts(207) == []
    assert loop.queue_item(207).draft_state == "none"
