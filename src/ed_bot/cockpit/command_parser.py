"""Turn typed chat text into a UserCommand.

A small, deterministic parser for the common verbs; anything unrecognized
becomes a ``freeform`` command for the agent to interpret. The optional
``active_thread`` lets bare commands ("post it", "make it more Socratic")
target the thread currently open in the draft viewer."""
from __future__ import annotations

import re
from typing import Optional

from ed_bot.cockpit.models import UserCommand

_NUM = re.compile(r"#?(\d{1,6})")


def _first_number(text: str) -> Optional[int]:
    m = _NUM.search(text)
    return int(m.group(1)) if m else None


def parse_command(text: str, *, active_thread: Optional[int] = None) -> UserCommand:
    t = text.strip()
    low = t.lower()

    if "check" in low and "forum" in low:
        return UserCommand(intent="check_forum")

    if low.startswith(("answer", "open", "show", "draft")):
        return UserCommand(intent="open", thread=_first_number(t) or active_thread)

    if low in ("post it", "post", "approve", "send it", "ship it"):
        return UserCommand(intent="approve", thread=active_thread)

    if low in ("reject", "discard"):
        return UserCommand(intent="reject", thread=active_thread)

    if low in ("flag", "needs human", "flag for human"):
        return UserCommand(intent="flag", thread=active_thread)

    if low in ("skip", "next"):
        return UserCommand(intent="skip", thread=active_thread)

    if low.startswith(("make it", "edit", "revise", "redo", "more ", "less ")):
        return UserCommand(intent="edit", thread=active_thread, text=t)

    return UserCommand(intent="freeform", thread=active_thread, text=t)
