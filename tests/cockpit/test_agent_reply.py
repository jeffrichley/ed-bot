"""draft_reply targets a specific comment (or the OP) with deterministic routing."""
import pytest

from ed_bot.cockpit import agent
from ed_bot.cockpit.models import DraftPayload

pytestmark = pytest.mark.anyio


async def test_reply_to_op_is_a_top_level_answer():
    captured = {}

    async def fake_sdk_query(*, prompt, schema, cwd):
        captured["prompt"] = prompt
        # The model returns a wrong post_kind/target on purpose; we override it.
        return DraftPayload(thread_id=8100188, number=188, question="q",
                            body="answer body", post_kind="reply",
                            target_comment_id=999).model_dump()

    out = await agent.draft_reply(number=188, cwd=".", course_id=99,
                                  target_comment_id=None,
                                  sdk_query=fake_sdk_query,
                                  guardrail_scan=lambda b, p: [])
    assert out.post_kind == "answer"
    assert out.target_comment_id is None
    assert "original question" in captured["prompt"]


async def test_reply_to_comment_sets_reply_and_target():
    captured = {}

    async def fake_sdk_query(*, prompt, schema, cwd):
        captured["prompt"] = prompt
        return DraftPayload(thread_id=8100188, number=188, question="q",
                            body="reply body").model_dump()

    out = await agent.draft_reply(number=188, cwd=".", course_id=99,
                                  target_comment_id=18742738,
                                  sdk_query=fake_sdk_query,
                                  guardrail_scan=lambda b, p: [])
    assert out.post_kind == "reply"
    assert out.target_comment_id == 18742738
    assert "18742738" in captured["prompt"]


async def test_reply_attaches_guardrail_warnings():
    async def fake_sdk_query(*, prompt, schema, cwd):
        return DraftPayload(thread_id=1, number=1, question="q", body="b",
                            project="Project 1 - Martingale").model_dump()

    out = await agent.draft_reply(number=1, cwd=".", course_id=99,
                                  target_comment_id=5,
                                  sdk_query=fake_sdk_query,
                                  guardrail_scan=lambda b, p: ["leak 18/38"])
    assert out.guardrail_warnings == ["leak 18/38"]
