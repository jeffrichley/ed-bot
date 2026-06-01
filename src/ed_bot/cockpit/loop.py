"""The headless cockpit loop: one queue, one consumer/router, auto-draft.

Producers (the watcher task, user-command injection) hand messages to
``handle``. A new actionable WatcherEvent creates a QueueItem and auto-drafts
it; user commands act on existing items. Outbound typed results go to the
injected ``emit`` callback (Plan 3 wires it to Textual widgets)."""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional

from ed_bot.cockpit.models import (
    WatcherEvent, UserCommand, QueueItem, QueueUpdate, DraftPayload, StatusUpdate,
    ActionResult,
)

DraftFn = Callable[..., Awaitable[DraftPayload]]
Emit = Callable[[Any], None]
PostFn = Callable[..., Awaitable[ActionResult]]
IsAnsweredFn = Callable[[int], Awaitable[bool]]

_SILENT_CATEGORIES = {"Social >", "Announcements", "Articles | Papers | Media"}


class CockpitLoop:
    def __init__(self, *, cwd: str, course_id: int, draft_fn: DraftFn,
                 emit: Emit, post_fn: "PostFn | None" = None,
                 is_answered_fn: "IsAnsweredFn | None" = None) -> None:
        self._cwd = cwd
        self._course_id = course_id
        self._draft_fn = draft_fn
        self._emit = emit
        self._post_fn = post_fn
        self._is_answered_fn = is_answered_fn
        self._items: dict[int, QueueItem] = {}
        self._drafts: dict[int, DraftPayload] = {}

    # --- read accessors (Plan 3 / tests) ---
    def queue_item(self, number: int) -> Optional[QueueItem]:
        return self._items.get(number)

    def draft(self, number: int) -> Optional[DraftPayload]:
        return self._drafts.get(number)

    def _push_queue(self) -> None:
        self._emit(QueueUpdate(items=list(self._items.values())))

    def _is_actionable(self, ev: WatcherEvent) -> bool:
        if ev.kind in ("error", "recovered"):
            return False
        if ev.category in _SILENT_CATEGORIES and "?" not in ev.title:
            return False
        return True

    async def handle(self, msg: WatcherEvent | UserCommand):
        if isinstance(msg, WatcherEvent):
            return await self._on_event(msg)
        return await self._on_command(msg)

    async def _on_event(self, ev: WatcherEvent) -> None:
        if not self._is_actionable(ev):
            return
        item = QueueItem(
            thread_id=ev.thread_id, number=ev.number, title=ev.title,
            category=ev.category, kind=ev.kind,
            urgency="high" if ev.kind == "escalation" else "normal",
            draft_state="drafting", status="needs_attention",
        )
        self._items[ev.number] = item
        self._push_queue()
        await self._autodraft(ev.number)

    async def _autodraft(self, number: int) -> None:
        self._emit(StatusUpdate(line=f"drafting #{number}..."))
        try:
            payload = await self._draft_fn(
                number=number, cwd=self._cwd, course_id=self._course_id,
            )
        except Exception as e:  # noqa: BLE001 - surface as failed state
            self._items[number] = self._items[number].model_copy(
                update={"draft_state": "failed"})
            self._emit(StatusUpdate(line=f"draft #{number} failed: {e}"))
            self._push_queue()
            return
        self._drafts[number] = payload
        self._items[number] = self._items[number].model_copy(
            update={"draft_state": "ready"})
        self._emit(StatusUpdate(line=f"#{number} ready"))
        self._push_queue()

    async def _on_command(self, cmd: UserCommand):
        if cmd.intent == "open" and cmd.thread is not None:
            return self._drafts.get(cmd.thread)
        if cmd.intent == "approve" and cmd.thread is not None:
            return await self._approve(cmd.thread)
        return None

    async def _approve(self, number: int) -> ActionResult:
        payload = self._drafts.get(number)
        if payload is None:
            return ActionResult(thread_id=0, ok=False, message="no draft to post")
        if self._is_answered_fn is not None and await self._is_answered_fn(number):
            self._emit(StatusUpdate(line=f"#{number} already answered, skipped"))
            return ActionResult(thread_id=payload.thread_id, ok=False,
                                message="thread already answered, not posting")
        assert self._post_fn is not None, "post_fn required to approve"
        res = await self._post_fn(
            number=number, body=payload.body, post_kind=payload.post_kind,
            target_comment_id=payload.target_comment_id,
        )
        if res.ok:
            self._items[number] = self._items[number].model_copy(
                update={"status": "posted"})
            self._emit(StatusUpdate(line=f"posted #{number}"))
            self._push_queue()
        return res
