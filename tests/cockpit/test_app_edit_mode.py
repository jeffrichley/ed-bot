"""Direct draft editing: 'e' edits the draft box, Ctrl+S saves, Esc cancels."""
import pytest
from textual.widgets import TextArea

from ed_bot.cockpit.app import CockpitApp
from ed_bot.cockpit.widgets import QueueRail
from ed_bot.cockpit.models import WatcherEvent, DraftPayload

pytestmark = pytest.mark.anyio


def _make_app():
    async def draft_fn(*, number, **kw):
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question="q", body=f"body {number}",
                            original_content="student: help", confidence="HIGH")
    return CockpitApp(cwd=".", course_id=98559, draft_fn=draft_fn,
                      rescan_fn=lambda body, project: [])


async def _seed_and_open(app, pilot, number):
    await app.inject_event(WatcherEvent(
        kind="new_thread", thread_id=8100000 + number, number=number,
        title=f"t{number}", category="Project 1 | Martingale", url="u"))
    await pilot.pause()
    rail = app.query_one(QueueRail)
    rail.focus()
    await pilot.pause()
    rail.highlighted = 0
    await pilot.press("enter")
    for _ in range(5):
        await pilot.pause()


async def test_e_enters_edit_mode():
    app = _make_app()
    async with app.run_test() as pilot:
        await _seed_and_open(app, pilot, 207)
        assert app._active_thread == 207
        await pilot.press("e")
        await pilot.pause()
        draft = app.query_one("#draft", TextArea)
        assert app._editing is True
        assert draft.read_only is False
        assert app.focused is draft


async def test_ctrl_s_saves_edit_back_to_the_draft():
    app = _make_app()
    async with app.run_test() as pilot:
        await _seed_and_open(app, pilot, 207)
        await pilot.press("e")
        await pilot.pause()
        draft = app.query_one("#draft", TextArea)
        draft.text = "MANUALLY EDITED BODY"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app._editing is False
        assert draft.read_only is True
        assert app.loop.draft(207).body == "MANUALLY EDITED BODY"


async def test_escape_cancels_edit_and_reverts():
    app = _make_app()
    async with app.run_test() as pilot:
        await _seed_and_open(app, pilot, 207)
        original = app.loop.draft(207).body
        await pilot.press("e")
        await pilot.pause()
        draft = app.query_one("#draft", TextArea)
        draft.text = "SCRAPPED EDIT"
        await pilot.press("escape")
        await pilot.pause()
        assert app._editing is False
        assert app.loop.draft(207).body == original
        assert draft.text == original


async def test_e_without_active_draft_is_safe():
    app = _make_app()
    async with app.run_test() as pilot:
        app.query_one(QueueRail).focus()
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        assert app._editing is False
