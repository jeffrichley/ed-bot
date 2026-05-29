"""Tests for `ed review scan`'s _filter_actionable() helper."""
from ed_bot.cli.review import _filter_actionable


def _t(status, *, reply_grew=False, is_answered=True, thread_id=1):
    return {
        "thread_id": thread_id,
        "thread_number": thread_id,
        "title": "x",
        "category": "Project 1 | Martingale",
        "updated_at": "2026-05-28T10:00:00Z",
        "reply_count": 0,
        "is_answered": is_answered,
        "tracker_status": status,
        "reply_count_increased": reply_grew,
    }


def test_keeps_new_threads():
    assert _filter_actionable([_t("new")]) != []


def test_keeps_updated_since_answered():
    assert _filter_actionable([_t("updated_since_answered")]) != []


def test_keeps_needs_followup():
    assert _filter_actionable([_t("needs_followup")]) != []


def test_drops_updated_with_no_reply_growth_when_answered():
    """Existing behavior — answered + just an updated_at tick = noise."""
    assert _filter_actionable([_t("updated", is_answered=True, reply_grew=False)]) == []


def test_drops_updated_with_no_reply_growth_when_unanswered():
    """Regression: this used to pass through. Escalation #166 is unanswered
    AND its updated_at tick on every poll — without reply growth it should
    NOT appear as actionable."""
    assert _filter_actionable([_t("updated", is_answered=False, reply_grew=False)]) == []


def test_keeps_updated_with_reply_growth():
    """Reply count actually grew — real new activity, keep it."""
    assert _filter_actionable([_t("updated", reply_grew=True)]) != []


def test_mixed_list_filters_correctly():
    items = [
        _t("new", thread_id=1),
        _t("updated", thread_id=2, reply_grew=False, is_answered=False),  # drop (escalation noise)
        _t("updated", thread_id=3, reply_grew=True),  # keep
        _t("updated", thread_id=4, reply_grew=False, is_answered=True),  # drop
        _t("updated_since_answered", thread_id=5),
    ]
    kept = [t["thread_id"] for t in _filter_actionable(items)]
    assert kept == [1, 3, 5]
