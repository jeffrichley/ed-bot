"""Tests for the escalation alert banner."""
import pytest

from ed_bot.cockpit.app import CockpitApp
from ed_bot.cockpit.widgets import AlertBanner
from ed_bot.cockpit.models import WatcherEvent, DraftPayload


def _make_app():
    async def draft_fn(*, number, **kw):
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question="q", body="b", confidence="HIGH")
    return CockpitApp(cwd=".", course_id=98559, draft_fn=draft_fn,
                      post_fn=None, is_answered_fn=None, fetch_events=None)


@pytest.mark.anyio
async def test_escalation_flashes_alert_banner():
    app = _make_app()
    async with app.run_test() as pilot:
        await app.inject_event(WatcherEvent(
            kind="escalation", thread_id=8100166, number=166,
            title="Medical Emergency URGENT", category="Project 1 | Martingale",
            url="u"))
        await pilot.pause()
        banner = app.query_one(AlertBanner)
        assert banner.display is True
        assert "166" in str(banner.content) or "Medical" in str(banner.content)
