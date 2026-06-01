"""Tests for the entry-point wiring helpers (no live app run)."""
import pytest

from ed_bot.cockpit.__main__ import build_draft_fn


@pytest.mark.anyio
async def test_build_draft_fn_delegates_to_agent():
    calls = {}

    async def fake_draft_thread(*, number, cwd, course_id):
        calls["number"] = number
        from ed_bot.cockpit.models import DraftPayload
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question="q", body="b", confidence="HIGH")

    draft_fn = build_draft_fn(cwd="/ed", draft_thread=fake_draft_thread)
    payload = await draft_fn(number=207, cwd="/ignored", course_id=98559)
    assert calls["number"] == 207
    assert payload.number == 207
