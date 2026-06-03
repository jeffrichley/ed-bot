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
        assert any("📌" in l for l in labels)              # the original post
        assert any("🛡️" in l and "Steven" in l for l in labels)  # staff role
        assert any("🎓" in l and "Jane" in l for l in labels)     # student role
        # the follow-up is marked as needing a reply (❓) AND the draft target (✏️)
        assert any("❓" in l and "✏️" in l for l in labels)
        # the draft shows, and the comment box shows the targeted comment's text
        assert app.query_one("#draft", TextArea).text == "draft body"
        assert "follow-up question" in app.query_one("#comment", TextArea).text


async def test_navigating_tree_shows_each_comments_own_draft():
    op = CommentNode(
        comment_id=None, author="Jane", role="student", is_staff=False, text="OP",
        children=[
            CommentNode(comment_id=10, author="Bob", role="student",
                        is_staff=False, text="Q1", children=[], needs_reply=True),
            CommentNode(comment_id=20, author="Amy", role="student",
                        is_staff=False, text="Q2", children=[], needs_reply=True),
        ])

    async def draft_fn(*, number, **kw):  # unused on the per-comment path
        return DraftPayload(thread_id=8100207, number=number, question="q", body="x")

    async def draft_reply_fn(*, number, cwd, course_id, target_comment_id):
        return DraftPayload(thread_id=8100207, number=number, question="q",
                            body=f"reply to {target_comment_id}", post_kind="reply",
                            target_comment_id=target_comment_id)

    async def fetch_tree_fn(course_id, number):
        return op

    app = CockpitApp(cwd=".", course_id=98559, draft_fn=draft_fn,
                     fetch_tree_fn=fetch_tree_fn, draft_reply_fn=draft_reply_fn)
    async with app.run_test() as pilot:
        await _open(app, pilot, 207)
        labels = _all_labels(app.query_one("#tree", Tree).root)
        assert sum("✏️" in l for l in labels) == 2  # both questions drafted
        # Selecting comment 20 shows ITS draft.
        tree = app.query_one("#tree", Tree)
        tree.move_cursor(app._tree_nodes[20])
        for _ in range(4):
            await pilot.pause()
        assert app._active_target == 20
        assert app.query_one("#draft", TextArea).text == "reply to 20"


async def test_d_drafts_a_reply_on_demand_for_an_undrafted_comment():
    # Tree: only comment 10 is auto-drafted; the OP has no draft.
    op = CommentNode(
        comment_id=None, author="Jane", role="student", is_staff=False, text="OP",
        children=[CommentNode(comment_id=10, author="Bob", role="student",
                              is_staff=False, text="Q1", children=[],
                              needs_reply=True)])

    async def draft_fn(*, number, **kw):
        return DraftPayload(thread_id=8100207, number=number, question="q", body="x")

    async def draft_reply_fn(*, number, cwd, course_id, target_comment_id):
        return DraftPayload(thread_id=8100207, number=number, question="q",
                            body=f"reply to {target_comment_id}", post_kind="reply",
                            target_comment_id=target_comment_id)

    async def fetch_tree_fn(course_id, number):
        return op

    app = CockpitApp(cwd=".", course_id=98559, draft_fn=draft_fn,
                     fetch_tree_fn=fetch_tree_fn, draft_reply_fn=draft_reply_fn)
    async with app.run_test() as pilot:
        await _open(app, pilot, 207)
        assert app.loop.draft(207, None) is None      # OP not auto-drafted
        # Select the OP node and draft a reply on demand.
        tree = app.query_one("#tree", Tree)
        tree.move_cursor(app._tree_nodes[None])
        await pilot.pause()
        assert app._active_target is None
        app.action_draft_reply_here()
        for _ in range(6):
            await pilot.pause()
        assert app.loop.draft(207, None) is not None   # drafted on demand
        assert app.loop.draft(207, None).body == "reply to None"


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
