"""Cockpit display widgets and their pure render helpers (Layout A).

The render helpers are module functions so they can be unit-tested without
mounting an app. The widgets are thin wrappers the app updates."""
from __future__ import annotations

from textual.widgets import Static, OptionList
from textual.widgets.option_list import Option
from textual.containers import VerticalScroll

from ed_bot.cockpit.models import QueueItem, DraftPayload, ChatMessage


def queue_option_text(item: QueueItem) -> str:
    """One line for the queue rail."""
    mark = "!" if item.kind == "escalation" else " "
    state = {
        "drafting": "drafting...",
        "ready": "ready",
        "flagged": "flagged",
        "failed": "failed",
        "none": "",
    }.get(item.draft_state, "")
    posted = " (posted)" if item.status == "posted" else ""
    return f"{mark} #{item.number} {item.title} [{state}]{posted}".rstrip()


# Backwards-compatible alias (older callers/tests).
render_queue_line = queue_option_text


def forum_text(d: DraftPayload) -> str:
    """The full forum thread (post + replies) for the read-only forum box, or the
    short question if the agent did not capture the thread text."""
    if d.original_content.strip():
        return d.original_content.strip()
    return f"Q: {d.question}"


def forum_box_title(d: DraftPayload) -> str:
    """Border title for the forum box."""
    return f"Forum #{d.number} · {d.project or 'unknown project'} · conf {d.confidence}"


def draft_advisory(d: DraftPayload) -> str:
    """Advisory line (Never-Reveal hits) for the draft box subtitle, or ""."""
    if d.guardrail_warnings:
        return "ADVISORY: " + "; ".join(d.guardrail_warnings)
    return ""


def render_chat_line(msg: ChatMessage) -> str:
    """Render a transcript turn: 'role ▸ text'.

    Multi-paragraph replies are collapsed to single-spaced lines (no stray blank
    lines) and continuation lines are indented under the role prefix so the
    turn reads as one block."""
    prefix = f"{msg.role} ▸ "
    indent = " " * len(prefix)
    raw_lines = msg.text.splitlines()
    # Drop blank lines that would otherwise show as empty gaps in the transcript.
    lines = [ln for ln in raw_lines if ln.strip()] or [""]
    out = [prefix + lines[0]]
    out += [indent + ln for ln in lines[1:]]
    return "\n".join(out)


class QueueRail(OptionList):
    """Left rail: a selectable list of actionable threads.

    Each option's id is the thread number (str). Re-rendering on a QueueUpdate
    preserves the current highlight so navigation isn't disrupted."""

    def show(self, items: list[QueueItem]) -> None:
        prev = self.highlighted
        self.clear_options()
        if not items:
            self.add_option(Option("(queue empty)", id="__empty__"))
            return
        for item in items:
            self.add_option(Option(queue_option_text(item), id=str(item.number)))
        if prev is not None and prev < len(items):
            self.highlighted = prev
        elif items:
            self.highlighted = 0




class StatusBar(Static):
    """One-line status of what the agent is doing."""

    def show(self, line: str) -> None:
        self.update(line)


class AlertBanner(Static):
    """Header flash for escalations. Hidden unless an alert is active."""

    def flash(self, text: str) -> None:
        self.update(f"  {text}  ")
        self.styles.display = "block"

    def clear_alert(self) -> None:
        self.update("")
        self.styles.display = "none"


class ChatLog(VerticalScroll):
    """Scrollable transcript of you/ed-bot turns."""

    can_focus = False

    def add(self, msg: ChatMessage) -> None:
        line = Static(render_chat_line(msg))
        self.mount(line)
        line.scroll_visible()
