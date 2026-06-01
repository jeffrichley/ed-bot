"""Cockpit display widgets and their pure render helpers (Layout A).

The render helpers are module functions so they can be unit-tested without
mounting an app. The widgets are thin wrappers the app updates."""
from __future__ import annotations

from textual.widgets import Static

from ed_bot.cockpit.models import QueueItem, DraftPayload


def render_queue_line(item: QueueItem) -> str:
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


def render_draft(d: DraftPayload) -> str:
    """The center-panel text for a selected draft."""
    lines = [
        f"#{d.number}  ({d.project or 'unknown project'})  conf: {d.confidence}",
        "",
        f"Q: {d.question}",
        "",
        d.body,
    ]
    if d.guardrails_checked:
        lines += ["", f"guardrails checked: {', '.join(d.guardrails_checked)}"]
    if d.guardrail_warnings:
        lines += ["", "ADVISORY:"]
        lines += [f"  - {w}" for w in d.guardrail_warnings]
    lines += ["", "[a]pprove  [e]dit  [r]eject  [f]lag  [s]kip"]
    return "\n".join(lines)


class QueueRail(Static):
    """Left rail: the list of actionable threads."""

    def show(self, items: list[QueueItem]) -> None:
        if not items:
            self.update("(queue empty)")
            return
        self.update("\n".join(render_queue_line(i) for i in items))


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
