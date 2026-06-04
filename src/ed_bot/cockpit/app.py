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
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Input, TextArea, Tree
from textual import work

from ed_bot.cockpit.command_parser import parse_command
from ed_bot.cockpit.loop import CockpitLoop
from ed_bot.cockpit.watcher import watch_loop
from ed_bot.cockpit.messages import LoopEmission
from ed_bot.cockpit.models import (
    WatcherEvent, UserCommand, QueueUpdate, StatusUpdate, ActionResult, ChatMessage,
    DraftPayload,
)
from ed_bot.cockpit.widgets import (
    QueueRail, StatusBar, AlertBanner, ChatLog, forum_text, draft_advisory,
)


class CockpitApp(App):
    CSS_PATH = "app.tcss"
    BINDINGS = [
        ("a", "act('approve')", "approve"),
        ("e", "edit_draft", "edit"),
        ("r", "act('reject')", "reject"),
        ("f", "act('flag')", "flag"),
        ("s", "act('skip')", "skip"),
        ("d", "draft_reply_here", "draft reply here"),
        ("o", "open_browser", "open in browser"),
        ("ctrl+s", "save_draft", "save"),
        ("escape", "toggle_focus", "chat / actions"),
    ]

    def __init__(self, *, cwd: str, course_id: int, draft_fn,
                 post_fn=None, is_answered_fn=None, fetch_events=None,
                 chat_fn=None, chat_edit_fn=None, rescan_fn=None,
                 persist_fn=None, fetch_tree_fn=None, draft_reply_fn=None,
                 on_draft_ready=None, post_log_fn=None,
                 watch_interval: float = 120.0) -> None:
        super().__init__()
        self._fetch_events = fetch_events
        self._course_id = course_id
        self._watch_interval = watch_interval
        self._watch_stop: Optional[asyncio.Event] = None
        self._watch_queue: Optional[asyncio.Queue] = None
        self._active_thread: Optional[int] = None
        self._active_target: Optional[int] = None  # selected comment (None = OP)
        self._editing: bool = False
        self._edit_backup: str = ""
        self._tree_nodes: dict = {}        # comment_id -> TreeNode
        self._populating: bool = False     # ignore tree highlights while building
        self._pending_target: Optional[int] = None
        self.loop = CockpitLoop(
            cwd=cwd, course_id=course_id, draft_fn=draft_fn,
            emit=self._emit, post_fn=post_fn, is_answered_fn=is_answered_fn,
            chat_fn=chat_fn, chat_edit_fn=chat_edit_fn, rescan_fn=rescan_fn,
            persist_fn=persist_fn, fetch_tree_fn=fetch_tree_fn,
            draft_reply_fn=draft_reply_fn, on_draft_ready=on_draft_ready,
            post_log_fn=post_log_fn,
        )

    def compose(self) -> ComposeResult:
        yield Header()
        yield AlertBanner(id="alert")
        with Horizontal(id="body"):
            yield QueueRail(id="queue")
            yield Tree("thread", id="tree")
            with Vertical(id="right"):
                yield TextArea("", id="comment", read_only=True, soft_wrap=True)
                yield TextArea("", id="draft", read_only=True, soft_wrap=True)
        yield StatusBar(id="status")
        yield ChatLog(id="chatlog")
        yield Input(placeholder="type a command (e.g. 'post it')", id="chat")
        yield Footer()

    def on_mount(self) -> None:
        """Paint initial placeholder state so the panels aren't blank, and put
        keyboard focus on the chat input (not the now-focusable queue rail)."""
        self.query_one(QueueRail).show([])
        self.query_one("#tree", Tree).show_root = False
        self.query_one("#comment", TextArea).border_title = "Comment"
        self.query_one("#draft", TextArea).border_title = "Draft"
        self.query_one(StatusBar).show("ready")
        self.query_one("#chat", Input).focus()
        if self._fetch_events is not None:
            self._watch_stop = asyncio.Event()
            self._watch_queue = asyncio.Queue()
            self.sub_title = f"watching · starting · every {int(self._watch_interval)}s"
            self._run_watch_producer()
            self._run_watch_consumer()
        else:
            self.sub_title = "not watching (--no-watch)"

    # --- draft display ---
    def _show_draft(self, d: DraftPayload) -> None:
        """Populate the comment tree for this draft's thread and select the
        comment it targets; the tree selection drives the comment + draft panes.
        Skipped while editing so an in-flight edit isn't clobbered."""
        if self._editing:
            return
        self._populate_tree(d)

    def _populate_tree(self, d: DraftPayload) -> None:
        tree = self.query_one("#tree", Tree)
        tree.clear()
        self._tree_nodes = {}  # comment_id -> TreeNode
        op = self.loop.tree(d.number)
        if op is None:
            # No structured tree (fetch failed) -> fall back to the flat text.
            tree.root.set_label(f"#{d.number}")
            self._show_comment_text("Thread", forum_text(d))
            self._set_draft_box(d)
            return
        drafted = set(self.loop.targets_with_drafts(d.number))
        tree.root.set_label(f"#{d.number}  ({len(drafted)} draft(s))")
        self._populating = True
        self._add_node(tree.root, op, drafted=drafted)
        tree.root.expand_all()
        # Show the targeted comment now (the layout's stray highlight events are
        # ignored while _populating); then move the cursor to it after a refresh.
        target_tn = (self._tree_nodes.get(d.target_comment_id)
                     or self._tree_nodes.get(None))
        if target_tn is not None:
            self._select_comment(target_tn.data)
        self._pending_target = d.target_comment_id
        self.call_after_refresh(self._focus_target)

    def _focus_target(self) -> None:
        self._populating = False
        tn = (self._tree_nodes.get(self._pending_target)
              or self._tree_nodes.get(None))
        if tn is not None:
            tree = self.query_one("#tree", Tree)
            try:
                tree.move_cursor(tn)
            except Exception:  # noqa: BLE001 - cursor move is best-effort
                pass
            self._select_comment(tn.data)

    def _add_node(self, parent, cn, *, drafted) -> None:
        node = parent.add(self._node_label(cn, drafted), data=cn, expand=True)
        self._tree_nodes[cn.comment_id] = node
        for child in cn.children:
            self._add_node(node, child, drafted=drafted)

    # Compact tree labels: role + markers as emoji to save horizontal room.
    # 🎓 student · 🛡️ staff · 📌 original post · ❓ open question · ✏️ has a draft
    @staticmethod
    def _node_label(cn, drafted) -> str:
        role_icon = "🛡️" if cn.is_staff else "🎓"
        who = f"{role_icon} {cn.author}"
        if cn.is_op:
            who = f"📌 {who}"
        marks = ""
        if cn.needs_reply:
            marks += " ❓"
        if cn.comment_id in drafted:
            marks += " ✏️"
        return who + marks

    def _select_comment(self, cn) -> None:
        """Make this comment the active target: show its text and its draft."""
        self._active_target = cn.comment_id
        self._show_comment(cn)
        if self._editing:
            return
        d = (self.loop.draft(self._active_thread, cn.comment_id)
             if self._active_thread is not None else None)
        if d is not None:
            self._set_draft_box(d)
        else:
            box = self.query_one("#draft", TextArea)
            box.text = ""
            box.border_subtitle = ""
            box.border_title = "Draft — none here (press d to draft a reply)"

    def _set_draft_box(self, d: DraftPayload) -> None:
        box = self.query_one("#draft", TextArea)
        box.text = d.body
        box.border_subtitle = draft_advisory(d)
        kind = "answer to the post" if d.post_kind == "answer" else "reply"
        box.border_title = f"Draft → {kind}  ·  conf {d.confidence}"

    def _show_comment(self, cn) -> None:
        title = "Original post" if cn.is_op else f"{cn.author} ({cn.role})"
        self._show_comment_text(title, cn.text or "(no text)")

    def _show_comment_text(self, title: str, text: str) -> None:
        box = self.query_one("#comment", TextArea)
        box.text = text
        box.border_title = title

    def _clear_panes(self) -> None:
        """Reset the tree, comment, and draft panes to their empty state and
        forget the active thread/target. Used when the open thread leaves the
        queue (posted or rejected) and there is nothing to advance to."""
        tree = self.query_one("#tree", Tree)
        tree.clear()
        tree.root.set_label("thread")
        self._tree_nodes = {}
        comment = self.query_one("#comment", TextArea)
        comment.text = ""
        comment.border_title = "Comment"
        draft = self.query_one("#draft", TextArea)
        draft.text = ""
        draft.border_subtitle = ""
        draft.border_title = "Draft"
        self._active_thread = None
        self._active_target = None

    def _reconcile_active_after_queue(self, items) -> None:
        """When the open thread is gone from the rail (it was posted or
        rejected), advance to the next queued thread, or clear the panes if the
        queue is now empty. Leaves an in-progress edit untouched."""
        if self._editing or self._active_thread is None:
            return
        if any(i.number == self._active_thread for i in items):
            return  # the open thread is still queued — nothing to do
        self._clear_panes()
        if items:
            # Open the next thread so the panes follow the queue instead of
            # stranding the user on a blank view.
            self.inject_command(UserCommand(intent="open", thread=items[0].number))

    def on_tree_node_highlighted(self, event) -> None:
        """Arrowing the tree selects that comment: shows its text and its draft."""
        if self._populating:
            return  # ignore the layout's initial highlight events
        cn = getattr(event.node, "data", None)
        if cn is not None:
            self._select_comment(cn)

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
            self._reconcile_active_after_queue(payload.items)
        elif isinstance(payload, StatusUpdate):
            self.query_one(StatusBar).show(payload.line)
        elif isinstance(payload, ActionResult):
            if payload.ok:
                # Surface a warning on success too (e.g. posted but could not be
                # accepted on a post-type thread -> the human must resolve it).
                msg = f"posted — {payload.message}" if payload.message else "posted"
            else:
                msg = f"not posted: {payload.message}"
            self.query_one(StatusBar).show(msg)
        elif isinstance(payload, ChatMessage):
            self.query_one(ChatLog).add(payload)
        elif isinstance(payload, DraftPayload):
            # A chat edit revised the active draft -> refresh the viewer.
            if payload.number == self._active_thread:
                self._show_draft(payload)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        self.query_one(ChatLog).add(ChatMessage(role="you", text=text))
        cmd = parse_command(text, active_thread=self._active_thread)
        cmd = cmd.model_copy(update={"target": self._active_target})
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
        """Esc: in edit mode, cancel the edit; otherwise switch focus between the
        chat box (typing) and the queue (action hotkeys)."""
        if self._editing:
            draft = self.query_one("#draft", TextArea)
            draft.text = self._edit_backup  # revert
            self._exit_edit_mode()
            self.query_one(StatusBar).show("edit canceled")
            return
        chat = self.query_one("#chat", Input)
        if self.focused is chat:
            self.query_one(QueueRail).focus()
        else:
            chat.focus()

    def action_edit_draft(self) -> None:
        """Enter edit mode: make the draft box editable and focus it."""
        if (self._active_thread is None
                or self.loop.draft(self._active_thread, self._active_target) is None):
            self.query_one(StatusBar).show("no active draft to edit")
            return
        draft = self.query_one("#draft", TextArea)
        self._edit_backup = draft.text
        self._editing = True
        draft.read_only = False
        draft.border_title = "Draft — EDITING (^S save · Esc cancel)"
        draft.focus()

    def action_save_draft(self) -> None:
        """Ctrl+S: write the edited text back to the draft and exit edit mode."""
        if not self._editing:
            return
        new_body = self.query_one("#draft", TextArea).text
        updated = self.loop.update_draft_body(self._active_thread, new_body,
                                              self._active_target)
        self._exit_edit_mode()
        if updated is not None:
            self._show_draft(updated)
            self.query_one(StatusBar).show(f"saved draft #{self._active_thread}")

    def _exit_edit_mode(self) -> None:
        draft = self.query_one("#draft", TextArea)
        draft.read_only = True
        draft.border_title = "Draft"
        self._editing = False
        self.query_one(QueueRail).focus()

    def action_act(self, intent: str) -> None:
        if self._active_thread is None:
            self.query_one(StatusBar).show("no active thread")
            return
        self.inject_command(UserCommand(intent=intent, thread=self._active_thread,
                                        target=self._active_target))

    def action_draft_reply_here(self) -> None:
        """`d`: draft a reply for the selected comment if it has none yet."""
        if self._active_thread is None:
            self.query_one(StatusBar).show("no active thread")
            return
        if self.loop.draft(self._active_thread, self._active_target) is not None:
            self.query_one(StatusBar).show("this comment already has a draft")
            return
        self._draft_one_worker(self._active_thread, self._active_target)

    @work(group="draft")
    async def _draft_one_worker(self, number: int, target) -> None:
        self.query_one(StatusBar).show(f"drafting a reply for #{number}...")
        payload = await self.loop.draft_one(number, target)
        if not self.is_running or not self._screen_stack:
            return
        if payload is not None and number == self._active_thread:
            self._show_draft(payload)
            self.query_one(StatusBar).show(f"drafted a reply for #{number}")
        elif payload is None:
            self.query_one(StatusBar).show(f"could not draft a reply for #{number}")

    def _thread_url(self, number: int) -> Optional[str]:
        """The EdStem discussion URL for a queued thread number, or None if the
        thread isn't in the queue (we need its global thread_id)."""
        item = self.loop.queue_item(number)
        if item is None:
            return None
        return (f"https://edstem.org/us/courses/{self._course_id}"
                f"/discussion/{item.thread_id}")

    def _target_thread_number(self) -> Optional[int]:
        """The thread to act on: the one highlighted in the queue, else the
        open draft. Uses the highlight so open-in-browser works as soon as a
        thread is queued, even while it is still drafting."""
        rail = self.query_one(QueueRail)
        idx = rail.highlighted
        if idx is not None:
            try:
                option = rail.get_option_at_index(idx)
            except Exception:  # noqa: BLE001 - index can be stale mid-rebuild
                option = None
            if option is not None and option.id not in (None, "__empty__"):
                return int(option.id)
        return self._active_thread

    def action_open_browser(self) -> None:
        """Open the highlighted (or active) thread in the default web browser.

        Works while a thread is still drafting: the URL needs only the thread's
        global id, which the queue item carries from the moment it is queued."""
        number = self._target_thread_number()
        url = self._thread_url(number) if number is not None else None
        if url is None:
            self.query_one(StatusBar).show("no thread to open")
            return
        webbrowser.open(url)
        self.query_one(StatusBar).show(f"opened #{number} in browser")

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
            on_poll=self._on_poll_tick,
        )

    def _on_poll_tick(self) -> None:
        """Heartbeat: stamp the header so the operator can see polling is alive."""
        from datetime import datetime
        now = datetime.now().strftime("%H:%M:%S")
        self.sub_title = (f"watching · last checked {now} · "
                          f"every {int(self._watch_interval)}s")

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
        if isinstance(result, DraftPayload):
            self._active_thread = result.number
            self._active_target = result.target_comment_id
            self._show_draft(result)
