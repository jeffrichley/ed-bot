"""The comment Tree: the loop stores it; the app renders it and the targeted
comment when a thread opens."""
import pytest
from textual.widgets import TextArea, Tree

from ed_bot.cockpit.app import CockpitApp
from ed_bot.cockpit.loop import CockpitLoop
from ed_bot.cockpit.widgets import QueueRail
from ed_bot.cockpit.thread_tree import CommentNode
from ed_bot.cockpit.models import WatcherEvent, DraftPayload

pytestmark = pytest.mark.anyio


def _tree():
    return CommentNode(
        comment_id=None, author="Jane", role="student", is_staff=False,
        text="OP question text", children=[
            CommentNode(comment_id=42, author="Steven", role="staff",
                        is_staff=True, text="staff reply",
                        children=[
                            CommentNode(comment_id=43, author="Jane",
                                        role="student", is_staff=False,
                                        text="follow-up question", children=[],
                                        needs_reply=True)])])


async def test_loop_stores_tree_after_drafting():
    op = _tree()

    async def draft_fn(*, number, cwd, course_id):
        return DraftPayload(thread_id=8100207, number=number, question="q", body="b")

    async def fetch_tree_fn(course_id, number):
        return op

    loop = CockpitLoop(cwd=".", course_id=1, draft_fn=draft_fn,
                       emit=lambda e: None, fetch_tree_fn=fetch_tree_fn)
    await loop.handle(WatcherEvent(
        kind="new_thread", thread_id=8100207, number=207, title="t",
        category="Project 1 | Martingale", url="u"))
    assert loop.tree(207) is op


def _all_labels(node):
    out = [str(node.label)]
    for c in node.children:
        out += _all_labels(c)
    return out


async def _open(app, pilot, number):
    await app.inject_event(WatcherEvent(
        kind="new_thread", thread_id=8100000 + number, number=number, title="t",
        category="Project 1 | Martingale", url="u"))
    await pilot.pause()
    rail = app.query_one(QueueRail)
    rail.focus()
    await pilot.pause()
    rail.highlighted = 0
    await pilot.press("enter")
    for _ in range(6):
        await pilot.pause()


async def test_opening_thread_renders_tree_and_target_comment():
    op = _tree()

    async def draft_fn(*, number, cwd, course_id):
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question="q", body="draft body",
                            post_kind="reply", target_comment_id=43)

    async def fetch_tree_fn(course_id, number):
        return op

    app = CockpitApp(cwd=".", course_id=98559, draft_fn=draft_fn,
                     fetch_tree_fn=fetch_tree_fn)
    async with app.run_test() as pilot:
        await _open(app, pilot, 207)
        labels = _all_labels(app.query_one("#tree", Tree).root)
        assert any("Original post" in l for l in labels)
        assert any("Steven (staff)" in l for l in labels)
        # the follow-up is marked as needing a reply AND as the draft target
        assert any("needs reply" in l and "DRAFT" in l for l in labels)
        # the draft shows, and the comment box shows the targeted comment's text
        assert app.query_one("#draft", TextArea).text == "draft body"
        assert "follow-up question" in app.query_one("#comment", TextArea).text


async def test_top_level_answer_targets_the_op_comment():
    op = _tree()

    async def draft_fn(*, number, cwd, course_id):
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question="q", body="b", target_comment_id=None)

    async def fetch_tree_fn(course_id, number):
        return op

    app = CockpitApp(cwd=".", course_id=98559, draft_fn=draft_fn,
                     fetch_tree_fn=fetch_tree_fn)
    async with app.run_test() as pilot:
        await _open(app, pilot, 207)
        # target is None -> the comment box shows the original post.
        assert "OP question text" in app.query_one("#comment", TextArea).text
