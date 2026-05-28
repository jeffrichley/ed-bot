"""Tests for the classify() decision adapter."""
import pytest
from ed_bot.watch.classify import classify, Decision


def thread(**overrides):
    base = {
        "thread_id": 1,
        "number": 1,
        "title": "Help",
        "category": "Project 1 | Martingale",
        "is_answered": False,
        "is_pinned": False,
        "reply_count": 0,
        "updated_at": "2026-05-28T10:00:00Z",
        "body": "",
        "our_answer_id": None,
        "has_unanswered_followup": False,
    }
    base.update(overrides)
    return base


def test_pinned_threads_are_silent():
    assert classify(thread(is_pinned=True)).kind == "silent"


def test_social_without_question_is_silent():
    t = thread(category="Social >", title="Favorite restaurants", is_answered=False)
    assert classify(t).kind == "silent"


def test_social_with_question_mark_is_actionable():
    t = thread(category="Social >", title="Anyone in Atlanta?", is_answered=False)
    assert classify(t).kind == "new_thread"


def test_announcements_without_question_is_silent():
    t = thread(category="Announcements", title="Welcome", is_answered=False)
    assert classify(t).kind == "silent"


def test_already_answered_with_no_followup_is_silent():
    t = thread(is_answered=True, has_unanswered_followup=False)
    assert classify(t).kind == "silent"


def test_already_answered_with_our_followup_is_followup():
    t = thread(
        is_answered=True,
        our_answer_id=999,
        has_unanswered_followup=True,
    )
    assert classify(t).kind == "followup"


def test_new_question_is_new_thread():
    t = thread(category="Project 1 | Martingale", title="Q2 expected value")
    assert classify(t).kind == "new_thread"


def test_medical_emergency_is_escalation():
    t = thread(title="Medical Emergency URGENT - John")
    assert classify(t).kind == "escalation"


def test_integrity_keyword_is_escalation():
    t = thread(title="Academic integrity question")
    assert classify(t).kind == "escalation"


def test_regrade_keyword_is_escalation():
    t = thread(title="Regrade request for Project 1")
    assert classify(t).kind == "escalation"


def test_escalation_overrides_answered_state():
    t = thread(is_answered=True, title="Medical Emergency")
    assert classify(t).kind == "escalation"


def test_keyword_in_body_triggers_escalation():
    t = thread(title="Question about scoring", body="This is urgent - my dean said...")
    assert classify(t).kind == "escalation"


def test_keyword_word_boundary_required():
    # "urgent" as a standalone word matches; "regrademe" (extends past 'regrade')
    # must NOT match because the regex is word-bounded.
    t1 = thread(title="urgent question")
    assert classify(t1).kind == "escalation"
    t2 = thread(title="regrademe nonsense word")
    assert classify(t2).kind != "escalation"


def test_decision_carries_kind_and_thread_ref():
    t = thread(thread_id=42, number=10)
    d = classify(t)
    assert d.kind == "new_thread"
    assert d.thread["thread_id"] == 42
