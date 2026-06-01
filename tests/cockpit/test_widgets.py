"""Tests for the cockpit display widgets' pure render helpers."""
from ed_bot.cockpit.models import QueueItem, DraftPayload
from ed_bot.cockpit.widgets import render_queue_line, render_draft


def _item(**over):
    base = dict(thread_id=8100207, number=207, title="Figure 1 graph",
                category="Project 1 | Martingale", kind="new_thread",
                urgency="normal", draft_state="ready", status="needs_attention")
    base.update(over)
    return QueueItem(**base)


def test_render_queue_line_shows_number_and_title():
    line = render_queue_line(_item())
    assert "207" in line
    assert "Figure 1 graph" in line


def test_render_queue_line_marks_escalation():
    line = render_queue_line(_item(kind="escalation", urgency="high"))
    assert "!" in line  # escalation marker


def test_render_queue_line_shows_drafting_state():
    line = render_queue_line(_item(draft_state="drafting"))
    assert "drafting" in line.lower() or "..." in line


def test_render_draft_includes_question_body_and_confidence():
    d = DraftPayload(thread_id=8100207, number=207,
                     question="How is Figure 1 graded?",
                     body="The autograder checks returned values.",
                     confidence="HIGH", guardrails_checked=["martingale"])
    text = render_draft(d)
    assert "How is Figure 1 graded?" in text
    assert "The autograder checks returned values." in text
    assert "HIGH" in text


def test_render_draft_shows_guardrail_warnings():
    d = DraftPayload(thread_id=1, number=1, question="q", body="b",
                     guardrail_warnings=["possible Never-Reveal leak: 18/38"])
    text = render_draft(d)
    assert "18/38" in text
