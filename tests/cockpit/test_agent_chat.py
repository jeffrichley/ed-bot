"""Tests for the freeform chat_reply agent task (injected SDK, no network)."""
import pytest

from ed_bot.cockpit import agent


@pytest.mark.anyio
async def test_chat_reply_returns_agent_text():
    async def fake_sdk_text(*, prompt, cwd):
        assert "how many threads" in prompt.lower()
        return "There are 3 open threads."

    reply = await agent.chat_reply(
        text="how many threads are open?", cwd=".", course_id=98559,
        sdk_text=fake_sdk_text,
    )
    assert reply == "There are 3 open threads."


@pytest.mark.anyio
async def test_chat_reply_passes_course_context():
    seen = {}

    async def fake_sdk_text(*, prompt, cwd):
        seen["prompt"] = prompt
        return "ok"

    await agent.chat_reply(text="hi", cwd="/ed", course_id=98559,
                           sdk_text=fake_sdk_text)
    assert "98559" in seen["prompt"]
