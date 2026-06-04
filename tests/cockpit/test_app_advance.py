"""When the open thread leaves the queue (posted or rejected), the panes should
advance to the next thread or clear out instead of stranding stale content."""
import pytest

from textual.widgets import TextArea

pytestmark = pytest.mark.anyio


async def _make_app():
    from ed_bot.cockpit.app import CockpitApp
    from ed_bot.cockpit.models import DraftPayload

    async def draft_fn(*, number, cwd, course_id):  # pragma: no cover - unused here
        return DraftPayload(thread_id=900 + number, number=number, question="q",
                            body="b", post_kind="answer")

    return CockpitApp(cwd=".", course_id=1, draft_fn=draft_fn, fetch_events=None)


def _emit_queue(app, items):
    from ed_bot.cockpit.messages import LoopEmission
    from ed_bot.cockpit.models import QueueUpdate
    app.post_message(LoopEmission(QueueUpdate(items=items)))


def _item(number):
    from ed_bot.cockpit.models import QueueItem
    return QueueItem(thread_id=900 + number, number=number, title=f"t{number}",
                     category="Project 1 | Martingale", kind="new_thread",
                     draft_state="ready", status="needs_attention")


async def test_empty_queue_clears_panes_when_active_thread_gone():
    app = await _make_app()
    async with app.run_test() as pilot:
        app._active_thread = 42
        app._active_target = None
        app.query_one("#draft", TextArea).text = "stale draft body"
        _emit_queue(app, [])
        await pilot.pause()
        assert app._active_thread is None
        assert app._active_target is None
        assert app.query_one("#draft", TextArea).text == ""
        assert app.query_one("#comment", TextArea).text == ""


async def test_active_thread_still_queued_leaves_panes_alone():
    app = await _make_app()
    async with app.run_test() as pilot:
        app._active_thread = 42
        app.query_one("#draft", TextArea).text = "keep me"
        _emit_queue(app, [_item(42)])  # 42 is still in the rail
        await pilot.pause()
        assert app._active_thread == 42
        assert app.query_one("#draft", TextArea).text == "keep me"
