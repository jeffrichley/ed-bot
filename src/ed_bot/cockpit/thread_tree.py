"""Build a navigable comment tree from an EdStem thread and identify which
comments actually need a reply (the cockpit's per-comment drafting model).

A TA does not reply to every comment. The actionable points are:
  - the original post, when NO staff has responded anywhere yet (one top-level
    answer addresses the thread), OR
  - each dangling student follow-up (a non-staff comment with no staff response
    anywhere in its subtree, at the end of its chain), once staff has engaged.

This mirrors the watcher's unanswered-follow-up detection. A thread that is
answered with no dangling follow-up yields no targets (nothing to draft).

The input is duck-typed (anything with the ed-api ThreadDetail / Comment shape):
``detail`` needs ``author`` / ``content`` / ``comments`` / ``users`` /
``is_answered``; each comment needs ``id`` / ``user_id`` / ``author`` /
``content`` / ``replies``; an author needs ``name`` / ``role`` / ``is_staff``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ed_api.content import ed_xml_to_markdown


@dataclass
class CommentNode:
    comment_id: Optional[int]  # None => the original post (OP)
    author: str
    role: str
    is_staff: bool
    text: str
    children: list["CommentNode"] = field(default_factory=list)
    needs_reply: bool = False

    @property
    def is_op(self) -> bool:
        return self.comment_id is None

    @property
    def post_kind(self) -> str:
        """How a reply to this node would be posted: a top-level answer for the
        OP, a nested reply for a comment."""
        return "answer" if self.comment_id is None else "reply"

    @property
    def target_comment_id(self) -> Optional[int]:
        return self.comment_id


def _text(xml: str | None) -> str:
    raw = xml or ""
    try:
        md = ed_xml_to_markdown(raw).strip()
    except Exception:  # noqa: BLE001 - fall back to the raw text on parse trouble
        md = ""
    return md or raw.strip()


def _author_of(obj, users: dict):
    author = getattr(obj, "author", None) or users.get(getattr(obj, "user_id", None))
    if author is None:
        return "Unknown", "student", False
    return (getattr(author, "name", "Unknown"),
            getattr(author, "role", "student"),
            bool(getattr(author, "is_staff", False)))


def _build_node(comment, users: dict) -> CommentNode:
    name, role, is_staff = _author_of(comment, users)
    return CommentNode(
        comment_id=comment.id, author=name, role=role, is_staff=is_staff,
        text=_text(getattr(comment, "content", "")),
        children=[_build_node(r, users) for r in (getattr(comment, "replies", None) or [])],
    )


def _has_staff(node: CommentNode) -> bool:
    """Whether any staff author appears at or below this node."""
    return node.is_staff or any(_has_staff(c) for c in node.children)


_ACK_PHRASES = (
    "thank", "thanks", "thx", "got it", "makes sense", "appreciate",
    "understood", "that helps", "that helped", "perfect", "cheers",
    "will do", "sounds good", "great, that", "ok thank", "okay thank",
)


def _is_acknowledgment(text: str) -> bool:
    """A short closing remark ('thanks', 'got it') that closes a thread rather
    than asking anything. Real follow-up questions are usually longer, so a long
    message that merely contains 'thanks' is NOT treated as an acknowledgment."""
    t = text.strip().lower()
    if not t or len(t) > 80:
        return False
    return any(p in t for p in _ACK_PHRASES)


def build_comment_tree(detail) -> CommentNode:
    """Return the OP node (``comment_id is None``) with the comment forest as its
    children, with ``needs_reply`` set on the OP/comments that need a draft."""
    name, role, is_staff = _author_of(detail, getattr(detail, "users", {}) or {})
    users = getattr(detail, "users", {}) or {}
    op = CommentNode(
        comment_id=None, author=name, role=role, is_staff=is_staff,
        text=_text(getattr(detail, "content", "")),
        children=[_build_node(c, users) for c in (getattr(detail, "comments", None) or [])],
    )
    _mark_actionable(op, is_answered=bool(getattr(detail, "is_answered", False)))
    return op


def _mark_actionable(op: CommentNode, *, is_answered: bool) -> None:
    staff_engaged = any(_has_staff(c) for c in op.children)
    if not is_answered and not staff_engaged:
        # No staff has responded anywhere: a single top-level answer addresses it.
        op.needs_reply = True
        return

    # Staff has engaged (or the thread is marked answered): the open points are
    # the dangling student follow-ups -- non-staff comments with no staff
    # response in their subtree, taking the deepest in each chain.
    def unanswered(node: CommentNode) -> bool:
        return not node.is_staff and not _has_staff(node)

    def visit(node: CommentNode) -> None:
        for c in node.children:
            if (unanswered(c) and not any(unanswered(gc) for gc in c.children)
                    and not _is_acknowledgment(c.text)):
                c.needs_reply = True
            visit(c)

    visit(op)


def actionable_targets(op: CommentNode) -> list[CommentNode]:
    """The nodes (OP and/or comments) that need a reply, in display order."""
    out: list[CommentNode] = []

    def visit(node: CommentNode) -> None:
        if node.needs_reply:
            out.append(node)
        for c in node.children:
            visit(c)

    visit(op)
    return out


def flatten(op: CommentNode) -> list[tuple[int, CommentNode]]:
    """(depth, node) pairs in display order, for rendering an indented tree."""
    out: list[tuple[int, CommentNode]] = []

    def visit(node: CommentNode, depth: int) -> None:
        out.append((depth, node))
        for c in node.children:
            visit(c, depth + 1)

    visit(op, 0)
    return out


def render_tree(op: CommentNode, *, target_comment_id: "int | None" = None,
                target_is_set: bool = True) -> str:
    """Indented plain-text rendering of the comment tree for the forum box.

    Each node shows ``Author (role)`` with markers: ``needs reply`` for a node
    the triage flagged, and ``DRAFT ANSWERS THIS`` for the node the current
    draft targets (the OP when ``target_comment_id`` is None). ``target_is_set``
    is False when no draft is active, so nothing is marked as the target."""
    lines: list[str] = []
    for depth, node in flatten(op):
        pad = "  " * depth
        who = "Original post — " if node.is_op else ""
        who += f"{node.author} ({node.role})"
        marks = []
        if node.needs_reply:
            marks.append("● needs reply")
        if target_is_set and node.comment_id == target_comment_id:
            marks.append("◄── DRAFT ANSWERS THIS")
        header = pad + who + ("    " + "  ".join(marks) if marks else "")
        lines.append(header)
        body = (node.text or "").strip() or "(no text)"
        for line in body.splitlines() or [""]:
            lines.append(pad + "    " + line)
        lines.append("")
    return "\n".join(lines).rstrip()
