"""The CockpitApp: Layout A Textual UI over the headless CockpitLoop.

The loop runs in the app's asyncio loop. Its ``emit`` callback wraps each
result in a ``LoopEmission`` and posts it; ``on_loop_emission`` routes by type
to the widgets. Forum events and user commands are fed to the loop via async
workers. (Hotkeys and chat input arrive in the next task.)"""
from __future__ import annotations

from typing import Any, Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Input
from textual import work

from ed_bot.cockpit.loop import CockpitLoop
from ed_bot.cockpit.messages import LoopEmission
from ed_bot.cockpit.models import (
    WatcherEvent, UserCommand, QueueUpdate, StatusUpdate, ActionResult,
)
from ed_bot.cockpit.widgets import QueueRail, DraftViewer, StatusBar, AlertBanner


class CockpitApp(App):
    CSS_PATH = "app.tcss"

    def __init__(self, *, cwd: str, course_id: int, draft_fn,
                 post_fn=None, is_answered_fn=None, fetch_events=None) -> None:
        super().__init__()
        self._fetch_events = fetch_events
        self._active_thread: Optional[int] = None
        self.loop = CockpitLoop(
            cwd=cwd, course_id=course_id, draft_fn=draft_fn,
            emit=self._emit, post_fn=post_fn, is_answered_fn=is_answered_fn,
        )

    def compose(self) -> ComposeResult:
        yield Header()
        yield AlertBanner(id="alert")
        with Horizontal(id="body"):
            yield QueueRail(id="queue")
            yield DraftViewer(id="draft")
        yield StatusBar(id="status")
        yield Input(placeholder="type a command (e.g. 'post it')", id="chat")
        yield Footer()

    # --- loop -> UI bridge ---
    def _emit(self, payload: Any) -> None:
        """Sync callback handed to the loop; never touches widgets directly."""
        self.post_message(LoopEmission(payload))

    def on_loop_emission(self, message: LoopEmission) -> None:
        payload = message.payload
        if isinstance(payload, QueueUpdate):
            self.query_one(QueueRail).show(payload.items)
        elif isinstance(payload, StatusUpdate):
            self.query_one(StatusBar).show(payload.line)
        elif isinstance(payload, ActionResult):
            ok = "posted" if payload.ok else f"not posted: {payload.message}"
            self.query_one(StatusBar).show(ok)

    # --- feeding the loop ---
    async def inject_event(self, event: WatcherEvent) -> None:
        """Awaitable entry-point used by tests and the watcher task."""
        await self.loop.handle(event)

    @work()
    async def inject_command(self, cmd: UserCommand) -> None:
        result = await self.loop.handle(cmd)
        if result is None:
            return
        from ed_bot.cockpit.models import DraftPayload
        if isinstance(result, DraftPayload):
            self._active_thread = result.number
            self.query_one(DraftViewer).show(result)
