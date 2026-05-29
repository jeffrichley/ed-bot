"""Decide whether a thread update is actionable, and if so, which kind."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

Kind = Literal["new_thread", "followup", "escalation", "silent"]

_ESCALATION_RE = re.compile(
    r"\b(medical\s+emergency|integrity|regrade|dean|urgent)\b",
    re.IGNORECASE,
)

_SILENT_CATEGORIES = {"Social >", "Announcements", "Articles | Papers | Media"}


@dataclass
class Decision:
    kind: Kind
    thread: dict[str, Any]


def _matches_escalation(thread: dict) -> bool:
    haystack = f"{thread.get('title','')}\n{(thread.get('body','') or '')[:500]}"
    return bool(_ESCALATION_RE.search(haystack))


def title_is_escalation(title: str) -> bool:
    """Title-only escalation check. The fetch layer uses this to decide whether
    an already-alerted thread always warrants a detail fetch, so staff-handling
    can be detected without relying on the drift-prone /ed-check reply counter."""
    return bool(_ESCALATION_RE.search(title or ""))


def classify(thread: dict) -> Decision:
    """Map a thread + tracker context to a Decision.

    The classifier is intentionally conservative: when in doubt, silent.
    """
    if thread.get("is_pinned"):
        return Decision("silent", thread)

    if _matches_escalation(thread):
        return Decision("escalation", thread)

    # Already answered: only fires when there's a follow-up on our reply.
    if thread.get("is_answered"):
        if thread.get("our_answer_id") and thread.get("has_unanswered_followup"):
            return Decision("followup", thread)
        return Decision("silent", thread)

    # Unanswered. Category gates.
    category = thread.get("category", "")
    has_question = "?" in (thread.get("title") or "")
    if category in _SILENT_CATEGORIES and not has_question:
        return Decision("silent", thread)

    return Decision("new_thread", thread)
