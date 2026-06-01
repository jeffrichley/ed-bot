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


def render_draft(d: DraftPayload) -> str:
    """The center-panel text for a selected draft: the original forum post, then
    the proposed answer. Action keys are NOT shown here — they live in the
    footer (the app's BINDINGS)."""
    lines = [
        f"#{d.number}  ({d.project or 'unknown project'})  conf: {d.confidence}",
    ]
    if d.original_content.strip():
        lines += ["", "─── ORIGINAL POST ───", d.original_content.strip()]
    else:
        lines += ["", f"Q: {d.question}"]
    lines += ["", "─── PROPOSED ANSWER ───", d.body]
    if d.guardrails_checked:
        lines += ["", f"guardrails checked: {', '.join(d.guardrails_checked)}"]
    if d.guardrail_warnings:
        lines += ["", "ADVISORY:"]
        lines += [f"  - {w}" for w in d.guardrail_warnings]
    return "\n".join(lines)


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


class DraftViewer(Static):
    """Center panel: the selected thread's draft."""

    def show(self, draft: DraftPayload | None) -> None:
        self.update(render_draft(draft) if draft else "(select a thread)")


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
