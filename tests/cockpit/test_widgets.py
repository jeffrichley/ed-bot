"""Tests for the cockpit display widgets' pure render helpers."""
from ed_bot.cockpit.models import QueueItem, DraftPayload
from ed_bot.cockpit.widgets import (
    render_queue_line, forum_text, forum_box_title, draft_advisory,
)


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


def test_forum_box_title_shows_number_project_confidence():
    d = DraftPayload(thread_id=8100207, number=207,
                     question="How is Figure 1 graded?", body="...",
                     project="Project 1 - Martingale", confidence="HIGH")
    title = forum_box_title(d)
    assert "207" in title
    assert "Martingale" in title
    assert "HIGH" in title


def test_forum_text_shows_full_thread_when_present():
    d = DraftPayload(thread_id=8100207, number=207, question="short paraphrase",
                     original_content="student: My report is 8 pages but page 8 "
                     "is blank.\n\nstaff: Please check the syllabus.",
                     body="You're fine, page 8 is blank.")
    text = forum_text(d)
    # The forum box shows the whole conversation, not just a paraphrase.
    assert "page 8 is blank" in text
    assert "Please check the syllabus." in text
    # The draft body does NOT bleed into the forum box.
    assert "You're fine" not in text


def test_forum_text_falls_back_to_question():
    d = DraftPayload(thread_id=1, number=1, question="What is the page limit?",
                     body="b", original_content="")
    assert "What is the page limit?" in forum_text(d)


def test_draft_advisory_lists_guardrail_warnings():
    d = DraftPayload(thread_id=1, number=1, question="q", body="b",
                     guardrail_warnings=["possible Never-Reveal leak: 18/38"])
    assert "18/38" in draft_advisory(d)
    # No warnings -> empty advisory.
    clean = DraftPayload(thread_id=1, number=1, question="q", body="b")
    assert draft_advisory(clean) == ""


def test_render_chat_line_formats_role_and_text():
    from ed_bot.cockpit.widgets import render_chat_line
    from ed_bot.cockpit.models import ChatMessage
    line = render_chat_line(ChatMessage(role="you", text="post it"))
    assert "you" in line
    assert "post it" in line
    bot = render_chat_line(ChatMessage(role="ed-bot", text="posted #207"))
    assert "ed-bot" in bot
    assert "posted #207" in bot


def test_render_chat_line_collapses_blank_lines_and_indents():
    from ed_bot.cockpit.widgets import render_chat_line
    from ed_bot.cockpit.models import ChatMessage
    msg = ChatMessage(role="ed-bot", text="First line.\n\nSecond paragraph.")
    rendered = render_chat_line(msg)
    lines = rendered.split("\n")
    assert "" not in lines  # no stray blank lines
    assert lines[0].startswith("ed-bot ▸ First line.")
    assert "Second paragraph." in lines[1]
    assert lines[1].startswith(" ")  # continuation indented


def test_queue_rail_is_option_list_and_renders_items():
    from textual.widgets import OptionList
    from ed_bot.cockpit.widgets import QueueRail, queue_option_text
    assert issubclass(QueueRail, OptionList)
    text = queue_option_text(_item(number=207, title="Figure 1 graph"))
    assert "207" in text and "Figure 1 graph" in text
