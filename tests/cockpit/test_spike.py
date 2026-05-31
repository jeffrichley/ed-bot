"""Unit tests for the spike's logic, with a fake SDK query (no network)."""
import pytest

from ed_bot.cockpit.models import WatcherEvent, DraftPayload
from ed_bot.cockpit.spike import draft_for_event


def _event():
    return WatcherEvent(
        kind="new_thread", thread_id=8104866, number=207,
        title="Figure 1 graph", category="Project 1 | Martingale",
        url="https://edstem.org/us/courses/98559/discussion/8104866",
    )


@pytest.mark.anyio
async def test_draft_for_event_returns_validated_payload():
    async def fake_sdk_query(*, prompt, schema, cwd):
        assert schema["type"] == "object"
        assert "207" in prompt
        return {
            "thread_id": 8104866, "number": 207,
            "question": "How does Gradescope check our chart output?",
            "body": "The autograder reads the returned values, not the image.",
            "is_canned": False, "project": "Project 1 - Martingale",
            "guardrails_checked": ["martingale"], "confidence": "HIGH",
            "post_kind": "answer", "target_comment_id": None,
        }

    payload = await draft_for_event(_event(), cwd=".", sdk_query=fake_sdk_query)
    assert isinstance(payload, DraftPayload)
    assert payload.number == 207
    assert payload.confidence == "HIGH"


@pytest.mark.anyio
async def test_draft_for_event_raises_on_schema_violation():
    async def bad_sdk_query(*, prompt, schema, cwd):
        return {"number": 207}  # missing required fields

    with pytest.raises(Exception):
        await draft_for_event(_event(), cwd=".", sdk_query=bad_sdk_query)
