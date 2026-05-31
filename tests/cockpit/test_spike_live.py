"""Live SDK integration test. Deselected by default; run with:

    .venv/Scripts/python.exe -m pytest tests/cockpit/test_spike_live.py -m live -s

Proves the Claude Agent SDK can run this project's skills and return a
schema-valid, humanized DraftPayload. Does NOT post anything to EdStem.
"""
import pytest

from ed_bot.cockpit.models import WatcherEvent, DraftPayload
from ed_bot.cockpit.spike import draft_for_event


@pytest.mark.live
@pytest.mark.anyio
async def test_live_draft_for_real_thread():
    event = WatcherEvent(
        kind="new_thread", thread_id=8104866, number=207,
        title="Figure 1 graph", category="Project 1 | Martingale",
        url="https://edstem.org/us/courses/98559/discussion/8104866",
    )

    payload = await draft_for_event(event, cwd=".")

    assert isinstance(payload, DraftPayload)
    assert payload.number == 207
    assert payload.body.strip(), "body must be non-empty"

    # Humanizer signature: the project bans em dashes. A humanized answer must
    # not contain one. Cheap proxy that the humanizer ran.
    assert "—" not in payload.body, "em dash present, humanizer likely skipped"

    print("\n--- LIVE DRAFT ---\n", payload.model_dump_json(indent=2))
