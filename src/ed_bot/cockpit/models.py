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


# --- Outbound from the agent to the UI ---

DraftState = Literal["drafting", "ready", "flagged", "failed", "none"]
ItemStatus = Literal["needs_attention", "posted", "dismissed"]
Urgency = Literal["normal", "high"]
Confidence = Literal["HIGH", "MEDIUM", "LOW"]
PostKind = Literal["answer", "reply"]


class QueueItem(BaseModel):
    """One row in the left-rail queue."""

    thread_id: int
    number: int
    title: str
    category: str
    kind: EventKind
    urgency: Urgency = "normal"
    draft_state: DraftState = "none"
    status: ItemStatus = "needs_attention"


class QueueUpdate(BaseModel):
    """The full set of queue items to reconcile into the rail."""

    items: list[QueueItem]


class DraftPayload(BaseModel):
    """A drafted reply for one thread. ``body`` is ALWAYS the final,
    post-humanizer text. There is deliberately no raw-draft field: the UI must
    never be able to display pre-humanizer content. ``guardrail_warnings`` is an
    advisory, non-blocking list of possible Never-Reveal hits to speed review."""

    thread_id: int
    number: int
    question: str
    body: str
    is_canned: bool = False
    project: Optional[str] = None
    guardrails_checked: list[str] = []
    confidence: Confidence = "MEDIUM"
    post_kind: PostKind = "answer"
    target_comment_id: Optional[int] = None
    guardrail_warnings: list[str] = []
    # The student's actual forum post (plain text), so the reviewer can read the
    # original alongside the draft. Not pre-humanizer content.
    original_content: str = ""


class StatusUpdate(BaseModel):
    """One line for the status bar."""

    line: str


class ActionResult(BaseModel):
    """Outcome of a post/accept action."""

    thread_id: int
    ok: bool
    posted_id: Optional[int] = None
    accepted: bool = False
    message: str = ""


class AlertBanner(BaseModel):
    """An escalation surfaced inline: triggers the header flash + sound."""

    thread_id: int
    number: int
    title: str
    text: str


ChatRole = Literal["you", "ed-bot"]


class ChatMessage(BaseModel):
    """One line in the chat transcript: a human ('you') or agent ('ed-bot')
    turn. Emitted by the loop and rendered in the ChatLog."""

    role: ChatRole
    text: str
