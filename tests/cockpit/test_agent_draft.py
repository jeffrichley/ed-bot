"""Tests for the draft_thread agent task with a fake SDK and fake guardrail scan."""
import pytest

from ed_bot.cockpit.models import DraftPayload
from ed_bot.cockpit import agent


def _raw_draft(**over):
    base = dict(
        thread_id=8104866, number=207, question="How is Figure 1 graded?",
        body="Plot 10 episodes with the required axis limits.",
        is_canned=False, project="Project 1 - Martingale",
        guardrails_checked=["martingale"], confidence="HIGH",
        post_kind="answer", target_comment_id=None,
    )
    base.update(over)
    return base


@pytest.mark.anyio
async def test_draft_thread_attaches_no_warnings_for_clean_body():
    async def fake_sdk(*, prompt, schema, cwd):
        assert "207" in prompt
        return _raw_draft()

    def fake_scan(body, gpath):
        return []

    payload = await agent.draft_thread(
        number=207, cwd=".", course_id=98559,
        sdk_query=fake_sdk, guardrail_scan=fake_scan,
    )
    assert isinstance(payload, DraftPayload)
    assert payload.guardrail_warnings == []


@pytest.mark.anyio
async def test_draft_thread_attaches_advisory_warnings():
    async def fake_sdk(*, prompt, schema, cwd):
        return _raw_draft(body="win probability is 18/38")

    def fake_scan(body, gpath):
        return ["possible Never-Reveal leak: 18/38"] if "18/38" in body else []

    payload = await agent.draft_thread(
        number=207, cwd=".", course_id=98559,
        sdk_query=fake_sdk, guardrail_scan=fake_scan,
    )
    assert payload.guardrail_warnings == ["possible Never-Reveal leak: 18/38"]
    # Advisory only: the draft is still returned, NOT blocked.
    assert payload.body == "win probability is 18/38"
