"""The headless cockpit loop: one queue, one consumer/router, auto-draft.

Producers (the watcher task, user-command injection) hand messages to
``handle``. A new actionable WatcherEvent creates a QueueItem and auto-drafts
it; user commands act on existing items. Outbound typed results go to the
injected ``emit`` callback (Plan 3 wires it to Textual widgets)."""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Optional

from ed_bot.cockpit.models import (
    WatcherEvent, UserCommand, QueueItem, QueueUpdate, DraftPayload, StatusUpdate,
    ActionResult, ChatMessage,
)

DraftFn = Callable[..., Awaitable[DraftPayload]]
Emit = Callable[[Any], None]
PostFn = Callable[..., Awaitable[ActionResult]]
IsAnsweredFn = Callable[[int], Awaitable[bool]]  # called with thread_id
ChatFn = Callable[..., Awaitable[str]]
# Edit-aware chat: returns {"reply": str, "revised_body": str | None}.
ChatEditFn = Callable[..., Awaitable[dict]]
# Re-scan a revised body against its project guardrails -> advisory warnings.
RescanFn = Callable[[str, Optional[str]], list[str]]
# Persist a draft (after an edit) so curated wording survives a restart.
PersistFn = Callable[[int, DraftPayload], None]

_SILENT_CATEGORIES = {"Social >", "Announcements", "Articles | Papers | Media"}


class CockpitLoop:
    def __init__(self, *, cwd: str, course_id: int, draft_fn: DraftFn,
                 emit: Emit, post_fn: "PostFn | None" = None,
                 is_answered_fn: "IsAnsweredFn | None" = None,
                 chat_fn: "ChatFn | None" = None,
                 chat_edit_fn: "ChatEditFn | None" = None,
                 rescan_fn: "RescanFn | None" = None,
                 persist_fn: "PersistFn | None" = None,
                 chat_history_limit: int = 20) -> None:
        self._cwd = cwd
        self._course_id = course_id
        self._draft_fn = draft_fn
        self._emit = emit
        self._post_fn = post_fn
        self._is_answered_fn = is_answered_fn
        self._chat_fn = chat_fn
        self._chat_edit_fn = chat_edit_fn
        self._rescan_fn = rescan_fn
        self._persist_fn = persist_fn
        self._items: dict[int, QueueItem] = {}
        self._drafts: dict[int, DraftPayload] = {}
        # Chat conversation memory: (role, text) per turn, role in you|ed-bot.
        # Capped at the last ``chat_history_limit`` turns so the prompt (and
        # cost) stays bounded over a long session.
        self._chat_history: list[tuple[str, str]] = []
        self._chat_history_limit = chat_history_limit
        # Serialize chat turns so concurrent submits can't race / answer out of
        # order, and so each turn sees the prior turns in history.
        self._chat_lock = asyncio.Lock()

    # --- read accessors (Plan 3 / tests) ---
    def queue_item(self, number: int) -> Optional[QueueItem]:
        return self._items.get(number)

    def draft(self, number: int) -> Optional[DraftPayload]:
        return self._drafts.get(number)

    def update_draft_body(self, number: int, new_body: str) -> Optional[DraftPayload]:
        """Replace a draft's body (e.g. after a manual edit), re-scanning the
        guardrail advisory. Returns the updated payload, or None if no draft."""
        draft = self._drafts.get(number)
        if draft is None:
            return None
        warnings = (self._rescan_fn(new_body, draft.project)
                    if self._rescan_fn is not None else draft.guardrail_warnings)
        updated = draft.model_copy(
            update={"body": new_body, "guardrail_warnings": warnings})
        self._drafts[number] = updated
        if self._persist_fn is not None:
            self._persist_fn(number, updated)
        return updated

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
        # The watcher/seed event carries the authoritative GLOBAL thread id.
        # The agent's returned thread_id is an unguided LLM value, so never
        # trust it for routing: reconcile to the queue item's id.
        item = self._items.get(number)
        if item is not None:
            payload = payload.model_copy(update={"thread_id": item.thread_id})
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
        if cmd.intent == "check_forum":
            self._emit_queue_summary()
            return None
        if cmd.intent == "freeform" and (
                self._chat_fn is not None or self._chat_edit_fn is not None):
            await self._handle_freeform(cmd.text or "", cmd.thread)
            return None
        return None

    async def _handle_freeform(self, text: str,
                               active_thread: Optional[int] = None) -> None:
        # The lock serializes turns: turn N appends to history before turn N+1
        # reads it, so replies stay in order and each sees prior context.
        async with self._chat_lock:
            history = list(self._chat_history)
            self._chat_history.append(("you", text))
            self._emit(StatusUpdate(line="ed-bot is thinking..."))
            draft = (self._drafts.get(active_thread)
                     if active_thread is not None else None)
            try:
                if draft is not None and self._chat_edit_fn is not None:
                    reply = await self._chat_edit_turn(text, history,
                                                       active_thread, draft)
                else:
                    reply = await self._chat_fn(
                        text=text, cwd=self._cwd, course_id=self._course_id,
                        history=history,
                    )
            finally:
                self._emit(StatusUpdate(line="ready"))
            self._chat_history.append(("ed-bot", reply))
            # Keep only the most recent turns so the prompt stays bounded.
            if len(self._chat_history) > self._chat_history_limit:
                self._chat_history = self._chat_history[-self._chat_history_limit:]
            self._emit(ChatMessage(role="ed-bot", text=reply))

    async def _chat_edit_turn(self, text: str, history: list[tuple[str, str]],
                              number: int, draft: DraftPayload) -> str:
        """Run an edit-aware chat turn against the active draft. If the agent
        returns a revised body, update the stored draft and re-emit it so the
        viewer refreshes. Returns the chat reply text."""
        result = await self._chat_edit_fn(
            text=text, cwd=self._cwd, course_id=self._course_id,
            history=history, thread_content=draft.original_content,
            current_body=draft.body,
        )
        reply = (result.get("reply") or "").strip()
        new_body = result.get("revised_body")
        if new_body:
            warnings = (self._rescan_fn(new_body, draft.project)
                        if self._rescan_fn is not None else draft.guardrail_warnings)
            updated = draft.model_copy(
                update={"body": new_body, "guardrail_warnings": warnings})
            self._drafts[number] = updated
            if self._persist_fn is not None:
                self._persist_fn(number, updated)
            self._emit(updated)  # the app re-shows it in the draft viewer
            if not reply:
                reply = f"Updated the draft for #{number}."
        return reply

    def _emit_queue_summary(self) -> None:
        items = list(self._items.values())
        if not items:
            self._emit(ChatMessage(role="ed-bot", text="The queue is empty."))
            return
        parts = [f"#{i.number} ({i.draft_state})" for i in items]
        self._emit(ChatMessage(
            role="ed-bot",
            text=f"{len(items)} in queue: " + ", ".join(parts)))

    async def _approve(self, number: int) -> ActionResult:
        payload = self._drafts.get(number)
        if payload is None:
            return ActionResult(thread_id=0, ok=False, message="no draft to post")
        # Staleness guard applies ONLY to new top-level answers. A follow-up
        # reply legitimately targets an already-answered thread, so is_answered
        # must not block it.
        if (payload.post_kind == "answer" and self._is_answered_fn is not None
                and await self._is_answered_fn(payload.thread_id)):
            self._emit(StatusUpdate(line=f"#{number} already answered, skipped"))
            return ActionResult(thread_id=payload.thread_id, ok=False,
                                message="thread already answered, not posting")
        assert self._post_fn is not None, "post_fn required to approve"
        res = await self._post_fn(
            thread_id=payload.thread_id, number=number, body=payload.body,
            post_kind=payload.post_kind, target_comment_id=payload.target_comment_id,
        )
        if res.ok and number in self._items:
            self._items[number] = self._items[number].model_copy(
                update={"status": "posted"})
            self._emit(StatusUpdate(line=f"posted #{number}"))
            self._push_queue()
        return res
