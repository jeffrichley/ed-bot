"""The comment tree + 'which comments need a reply' triage logic."""
from types import SimpleNamespace

from ed_bot.cockpit.thread_tree import (
    build_comment_tree, actionable_targets, flatten, render_tree,
)


def _user(name, role):
    is_staff = role in ("staff", "admin", "instructor")
    return SimpleNamespace(name=name, role=role, is_staff=is_staff)


_CID = iter(range(1000, 99999))


def _comment(author, text="...", replies=None):
    return SimpleNamespace(id=next(_CID), user_id=0, author=author,
                           content=text, replies=replies or [])


def _detail(op_author, comments, is_answered=False, content="OP question text"):
    return SimpleNamespace(author=op_author, content=content,
                           comments=comments, users={}, is_answered=is_answered)


JANE = _user("Jane", "student")
BOB = _user("Bob", "student")
STAFF = _user("Steven", "staff")


def test_tree_structure_and_authors():
    detail = _detail(JANE, [
        _comment(STAFF, "Each bet is independent.",
                 replies=[_comment(JANE, "So variance grows?")]),
        _comment(BOB, "Same question here."),
    ])
    op = build_comment_tree(detail)
    assert op.is_op and op.author == "Jane" and op.role == "student"
    assert len(op.children) == 2
    assert op.children[0].author == "Steven" and op.children[0].is_staff
    assert op.children[0].children[0].author == "Jane"
    assert op.children[1].author == "Bob"


def test_no_staff_anywhere_flags_the_op_only():
    # Student question, only student chatter, no staff, not answered -> answer OP.
    detail = _detail(JANE, [_comment(BOB, "I think it's X")], is_answered=False)
    op = build_comment_tree(detail)
    targets = actionable_targets(op)
    assert targets == [op]
    assert op.post_kind == "answer" and op.target_comment_id is None


def test_staff_engaged_flags_dangling_student_followup():
    follow = _comment(JANE, "But what about variance?")
    staff = _comment(STAFF, "Bets are independent.", replies=[follow])
    detail = _detail(JANE, [staff], is_answered=True)
    op = build_comment_tree(detail)
    targets = actionable_targets(op)
    assert targets == [follow_node(op, follow.id)]
    t = targets[0]
    assert t.post_kind == "reply" and t.target_comment_id == follow.id
    assert not op.needs_reply  # the OP is considered handled


def test_closing_thanks_is_not_flagged():
    # A short 'Thanks!' closes the thread; it must NOT be flagged as needing a
    # reply (this is the common real-world thread ending).
    staff = _comment(STAFF, "Here is the answer.",
                     replies=[_comment(JANE, "Thank you!", replies=[])])
    detail = _detail(JANE, [staff], is_answered=True)
    op = build_comment_tree(detail)
    assert actionable_targets(op) == []


def test_long_followup_mentioning_thanks_is_still_flagged():
    # "Thanks, but I'm still confused..." is a real question, not an acknowledgment.
    follow = _comment(JANE, "Thanks, but I'm still confused about how the "
                            "variance behaves as n grows. Could you clarify?")
    staff = _comment(STAFF, "Bets are independent.", replies=[follow])
    detail = _detail(JANE, [staff], is_answered=True)
    op = build_comment_tree(detail)
    assert [t.target_comment_id for t in actionable_targets(op)] == [follow.id]


def test_two_separate_unanswered_questions_flag_both():
    # Staff answered question B; question A from another student is untouched.
    a = _comment(BOB, "Unrelated question A")          # no staff under it
    b = _comment(JANE, "Question B",
                 replies=[_comment(STAFF, "Answer to B")])
    detail = _detail(JANE, [a, b], is_answered=True)
    op = build_comment_tree(detail)
    ids = {t.target_comment_id for t in actionable_targets(op)}
    assert a.id in ids        # A still needs a reply
    assert b.id not in ids    # B was answered by staff


def test_deepest_student_in_chain_is_the_target():
    # student -> student -> student (no staff): only the deepest is flagged.
    leaf = _comment(JANE, "third")
    mid = _comment(BOB, "second", replies=[leaf])
    detail = _detail(JANE, [_comment(JANE, "first", replies=[mid])],
                     is_answered=False)
    # No staff anywhere -> the OP is the single target (one answer covers it).
    op = build_comment_tree(detail)
    assert actionable_targets(op) == [op]


def test_flatten_gives_depth_ordered_nodes():
    detail = _detail(JANE, [_comment(STAFF, "a", replies=[_comment(JANE, "b")])])
    op = build_comment_tree(detail)
    flat = flatten(op)
    assert flat[0][0] == 0 and flat[0][1].is_op
    depths = [d for d, _ in flat]
    assert depths == [0, 1, 2]


def test_render_tree_indents_and_marks_target():
    follow = _comment(JANE, "But what about variance?")
    staff = _comment(STAFF, "Bets are independent.", replies=[follow])
    detail = _detail(JANE, [staff], is_answered=True, content="I'm confused")
    op = build_comment_tree(detail)
    out = render_tree(op, target_comment_id=follow.id)
    # OP at column 0, staff indented, follow-up indented further.
    lines = out.splitlines()
    assert lines[0].startswith("Original post")
    assert "Steven (staff)" in out
    # The targeted follow-up is marked; the staff comment is not.
    target_line = next(l for l in lines if "But what about variance" not in l
                       and "DRAFT ANSWERS THIS" in l)
    assert "Jane (student)" in target_line
    assert "Steven (staff)    ◄── DRAFT ANSWERS THIS" not in out
    # The follow-up was flagged as needing a reply.
    assert "needs reply" in out


def test_render_tree_no_target_marks_nothing():
    detail = _detail(JANE, [_comment(BOB, "hi")], is_answered=False)
    op = build_comment_tree(detail)
    out = render_tree(op, target_comment_id=None, target_is_set=False)
    assert "DRAFT ANSWERS THIS" not in out


# helper: find a node by comment id
def follow_node(op, cid):
    for _, n in flatten(op):
        if n.comment_id == cid:
            return n
    raise AssertionError(f"no node {cid}")
