"""The typed contract between the cockpit UI and the agent.

Every message into the agent and every structured result out of it is one of
these models. Outbound models are returned by the agent via the SDK's
``output_format`` structured-output mechanism, so the UI consumes validated
objects rather than parsing prose.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

# --- Inbound to the agent ---

CommandIntent = Literal[
    "check_forum", "open", "approve", "edit", "reject",
    "flag", "skip", "post_canned", "watcher_ctl", "freeform",
]

EventKind = Literal["new_thread", "followup", "escalation", "error", "recovered"]


class UserCommand(BaseModel):
    """A human action from the cockpit: a hotkey or typed natural language,
    normalized into a single shape. ``freeform`` carries arbitrary chat text
    for the agent to interpret."""

    intent: CommandIntent
    thread: Optional[int] = None
    text: Optional[str] = None


class WatcherEvent(BaseModel):
    """An actionable forum event produced by the watcher task."""

    kind: EventKind
    thread_id: int
    number: int
    title: str
    category: str
    url: str
