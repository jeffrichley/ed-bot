"""The CockpitApp: Layout A Textual UI over the headless CockpitLoop.

The loop runs in the app's asyncio loop. Its ``emit`` callback wraps each
result in a ``LoopEmission`` and posts it; ``on_loop_emission`` routes by type
to the widgets. Forum events and user commands are fed to the loop via async
workers. (Hotkeys and chat input arrive in the next task.)"""
from __future__ import annotations

import asyncio
import webbrowser
from typing import Any, Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Input
from textual import work

from ed_bot.cockpit.command_parser import parse_command
from ed_bot.cockpit.loop import CockpitLoop
from ed_bot.cockpit.watcher import watch_loop
from ed_bot.cockpit.messages import LoopEmission
from ed_bot.cockpit.models import (
    WatcherEvent, UserCommand, QueueUpdate, StatusUpdate, ActionResult, ChatMessage,
)
from ed_bot.cockpit.widgets import QueueRail, DraftViewer, StatusBar, AlertBanner, ChatLog


class CockpitApp(App):
    CSS_PATH = "app.tcss"
    BINDINGS = [
        ("a", "act('approve')", "approve"),
        ("e", "act('edit')", "edit"),
        ("r", "act('reject')", "reject"),
        ("f", "act('flag')", "flag"),
        ("s", "act('skip')", "skip"),
        ("o", "open_browser", "open in browser"),
        ("escape", "toggle_focus", "chat / actions"),
    ]

    def __init__(self, *, cwd: str, course_id: int, draft_fn,
                 post_fn=None, is_answered_fn=None, fetch_events=None,
                 chat_fn=None, watch_interval: float = 120.0) -> None:
        super().__init__()
        self._fetch_events = fetch_events
        self._course_id = course_id
        self._watch_interval = watch_interval
        self._watch_stop: Optional[asyncio.Event] = None
        self._watch_queue: Optional[asyncio.Queue] = None
        self._active_thread: Optional[int] = None
        self.loop = CockpitLoop(
            cwd=cwd, course_id=course_id, draft_fn=draft_fn,
            emit=self._emit, post_fn=post_fn, is_answered_fn=is_answered_fn,
            chat_fn=chat_fn,
        )

    def compose(self) -> ComposeResult:
        yield Header()
        yield AlertBanner(id="alert")
        with Horizontal(id="body"):
            yield QueueRail(id="queue")
            yield DraftViewer(id="draft")
        yield StatusBar(id="status")
        yield ChatLog(id="chatlog")
        yield Input(placeholder="type a command (e.g. 'post it')", id="chat")
        yield Footer()

    def on_mount(self) -> None:
        """Paint initial placeholder state so the panels aren't blank, and put
        keyboard focus on the chat input (not the now-focusable queue rail)."""
        self.query_one(QueueRail).show([])
        self.query_one(DraftViewer).show(None)
        self.query_one(StatusBar).show("ready")
        self.query_one("#chat", Input).focus()
        if self._fetch_events is not None:
            self._watch_stop = asyncio.Event()
            self._watch_queue = asyncio.Queue()
            self._run_watch_producer()
            self._run_watch_consumer()

    # --- loop -> UI bridge ---
    def _emit(self, payload: Any) -> None:
        """Sync callback handed to the loop; never touches widgets directly."""
        self.post_message(LoopEmission(payload))

    def on_loop_emission(self, message: LoopEmission) -> None:
        # A watcher draft can finish during teardown (app stopped, screen
        # detached). Its emission still rides the pump but the widgets are
        # gone, so query_one would raise NoMatches. Drop late emissions.
        if not self.is_running or not self._screen_stack:
            return
        payload = message.payload
        if isinstance(payload, QueueUpdate):
            self.query_one(QueueRail).show(payload.items)
            escalations = [
                i for i in payload.items
                if i.kind == "escalation" and i.status == "needs_attention"
            ]
            banner = self.query_one(AlertBanner)
            if escalations:
                top = escalations[0]
                banner.flash(f"ESCALATION #{top.number}: {top.title}")
            else:
                banner.clear_alert()
        elif isinstance(payload, StatusUpdate):
            self.query_one(StatusBar).show(payload.line)
        elif isinstance(payload, ActionResult):
            ok = "posted" if payload.ok else f"not posted: {payload.message}"
            self.query_one(StatusBar).show(ok)
        elif isinstance(payload, ChatMessage):
            self.query_one(ChatLog).add(payload)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        self.query_one(ChatLog).add(ChatMessage(role="you", text=text))
        cmd = parse_command(text, active_thread=self._active_thread)
        self.inject_command(cmd)

    def on_option_list_option_selected(self, event) -> None:
        """A queue item was chosen: open its draft (same as 'open N')."""
        option_id = event.option_id
        if option_id is None or option_id == "__empty__":
            return
        self.inject_command(UserCommand(intent="open", thread=int(option_id)))
        # Keep focus on the queue rail (action mode) so the a/e/r/f/s/o hotkeys
        # act on the thread you just opened. Press Esc to jump to the chat box.

    def action_toggle_focus(self) -> None:
        """Switch between the chat box (typing) and the queue (action hotkeys).

        The single-letter actions and the chat input share the keyboard, so we
        keep them in separate focus contexts: when the chat is focused you type,
        when the queue is focused a/e/r/f/s/o act. Esc flips between them."""
        chat = self.query_one("#chat", Input)
        if self.focused is chat:
            self.query_one(QueueRail).focus()
        else:
            chat.focus()

    def action_act(self, intent: str) -> None:
        if self._active_thread is None:
            self.query_one(StatusBar).show("no active thread")
            return
        self.inject_command(UserCommand(intent=intent, thread=self._active_thread))

    def _thread_url(self, number: int) -> Optional[str]:
        """The EdStem discussion URL for a queued thread number, or None if the
        thread isn't in the queue (we need its global thread_id)."""
        item = self.loop.queue_item(number)
        if item is None:
            return None
        return (f"https://edstem.org/us/courses/{self._course_id}"
                f"/discussion/{item.thread_id}")

    def action_open_browser(self) -> None:
        """Open the active thread in the default web browser."""
        if self._active_thread is None:
            self.query_one(StatusBar).show("no active thread to open")
            return
        url = self._thread_url(self._active_thread)
        if url is None:
            self.query_one(StatusBar).show("no thread to open")
            return
        webbrowser.open(url)
        self.query_one(StatusBar).show(f"opened #{self._active_thread} in browser")

    # --- feeding the loop ---
    async def inject_event(self, event: WatcherEvent) -> None:
        """Awaitable entry-point used by tests. NOTE: this awaits the auto-draft
        inline, so callers on the message pump (e.g. startup seeding) must use
        ``draft_event`` instead to avoid freezing the UI during the live SDK
        draft."""
        await self.loop.handle(event)

    @work(group="draft")
    async def draft_event(self, event: WatcherEvent) -> None:
        """Process a forum event (create queue item + auto-draft) on a
        background worker so the live SDK draft never blocks the message pump.
        Drafts for different events run concurrently."""
        await self.loop.handle(event)

    @work(group="watch")
    async def _run_watch_producer(self) -> None:
        """Poll the forum on an interval, putting events on the watch queue."""
        await watch_loop(
            course_id=self._course_id, queue=self._watch_queue,
            fetch_events=self._fetch_events,
            interval_seconds=self._watch_interval, stop=self._watch_stop,
        )

    @work(group="watch")
    async def _run_watch_consumer(self) -> None:
        """Drain polled events and draft each on the non-blocking draft worker."""
        while not self._watch_stop.is_set():
            ev = await self._watch_queue.get()
            self.draft_event(ev)

    def on_unmount(self) -> None:
        if self._watch_stop is not None:
            self._watch_stop.set()

    @work()
    async def inject_command(self, cmd: UserCommand) -> None:
        result = await self.loop.handle(cmd)
        if result is None:
            return
        from ed_bot.cockpit.models import DraftPayload
        if isinstance(result, DraftPayload):
            self._active_thread = result.number
            self.query_one(DraftViewer).show(result)
