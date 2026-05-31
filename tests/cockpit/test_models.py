"""Tests for the cockpit Pydantic contract."""
import pytest
from pydantic import ValidationError

from ed_bot.cockpit.models import UserCommand, WatcherEvent


def test_user_command_minimal():
    cmd = UserCommand(intent="check_forum")
    assert cmd.intent == "check_forum"
    assert cmd.thread is None
    assert cmd.text is None


def test_user_command_with_thread_and_text():
    cmd = UserCommand(intent="edit", thread=207, text="make it more Socratic")
    assert cmd.thread == 207
    assert cmd.text == "make it more Socratic"


def test_user_command_rejects_unknown_intent():
    with pytest.raises(ValidationError):
        UserCommand(intent="frobnicate")


def test_watcher_event_roundtrip():
    ev = WatcherEvent(
        kind="new_thread",
        thread_id=8104866,
        number=207,
        title="Figure 1 graph",
        category="Project 1 | Martingale",
        url="https://edstem.org/us/courses/98559/discussion/8104866",
    )
    assert ev.number == 207
    assert ev.kind == "new_thread"


def test_watcher_event_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        WatcherEvent(
            kind="meteor_strike",
            thread_id=1, number=1, title="x", category="y", url="z",
        )


from ed_bot.cockpit.models import (
    QueueItem, QueueUpdate, DraftPayload, StatusUpdate, ActionResult, AlertBanner,
)


def test_queue_item_defaults():
    item = QueueItem(
        thread_id=8104866, number=207, title="Figure 1 graph",
        category="Project 1 | Martingale", kind="new_thread",
    )
    assert item.urgency == "normal"
    assert item.draft_state == "none"
    assert item.status == "needs_attention"


def test_queue_update_holds_items():
    upd = QueueUpdate(items=[
        QueueItem(thread_id=1, number=1, title="a", category="c", kind="new_thread"),
    ])
    assert len(upd.items) == 1


def test_draft_payload_is_humanized_only():
    # The contract must NOT carry a raw / pre-humanizer field. The UI can only
    # ever receive the final body. Guard the invariant explicitly.
    fields = set(DraftPayload.model_fields)
    for forbidden in ("raw_body", "raw_draft", "pre_humanizer", "draft_raw"):
        assert forbidden not in fields, f"DraftPayload must not expose {forbidden}"
    assert "body" in fields


def test_draft_payload_roundtrip():
    d = DraftPayload(
        thread_id=8104866, number=207,
        question="How is Figure 1 graded?",
        body="The autograder checks returned values, not the PNG.",
        is_canned=False, project="Project 1 - Martingale",
        guardrails_checked=["martingale"], confidence="HIGH",
        post_kind="answer", target_comment_id=None,
    )
    assert d.confidence == "HIGH"
    assert d.post_kind == "answer"


def test_action_result_failure_shape():
    r = ActionResult(thread_id=1, ok=False, posted_id=None, accepted=False,
                     message="400 Bad Request")
    assert r.ok is False
    assert r.posted_id is None


def test_status_and_alert():
    assert StatusUpdate(line="drafting #207...").line.startswith("drafting")
    a = AlertBanner(thread_id=1, number=166, title="Medical Emergency", text="urgent")
    assert a.number == 166
