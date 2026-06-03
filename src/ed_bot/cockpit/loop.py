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
# Draft a reply to one comment (or the OP): (number, cwd, course_id, target).
DraftReplyFn = Callable[..., Awaitable[DraftPayload]]
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
# Fetch a thread's comment tree (CommentNode) for the tree view.
FetchTreeFn = Callable[[int, int], Awaitable[Any]]  # (course_id, number) -> CommentNode

_SILENT_CATEGORIES = {"Social >", "Announcements", "Articles | Papers | Media"}


class CockpitLoop:
    def __init__(self, *, cwd: str, course_id: int, draft_fn: DraftFn,
                 emit: Emit, post_fn: "PostFn | None" = None,
                 is_answered_fn: "IsAnsweredFn | None" = None,
                 chat_fn: "ChatFn | None" = None,
                 chat_edit_fn: "ChatEditFn | None" = None,
                 rescan_fn: "RescanFn | None" = None,
                 persist_fn: "PersistFn | None" = None,
                 fetch_tree_fn: "FetchTreeFn | None" = None,
                 draft_reply_fn: "DraftReplyFn | None" = None,
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
        self._fetch_tree_fn = fetch_tree_fn
        self._draft_reply_fn = draft_reply_fn
        self._items: dict[int, QueueItem] = {}
        # Drafts keyed by (thread number, target comment id). target None is the
        # top-level answer to the original post; a comment id is a reply to it.
        self._drafts: dict[tuple[int, Optional[int]], DraftPayload] = {}
        self._trees: dict[int, Any] = {}  # number -> CommentNode (the OP node)
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

    def draft(self, number: int,
              target: Optional[int] = None) -> Optional[DraftPayload]:
        return self._drafts.get((number, target))

    def targets_with_drafts(self, number: int) -> list[Optional[int]]:
        """The comment targets that have a draft for this thread."""
        return [tgt for (num, tgt) in self._drafts if num == number]

    def tree(self, number: int):
        """The thread's comment tree (CommentNode), or None if not fetched."""
        return self._trees.get(number)

    async def draft_one(self, number: int,
                        target: Optional[int]) -> Optional[DraftPayload]:
        """Draft a reply for one comment on demand (the `d` action). Returns the
        stored payload, or None if there is no reply fn or the draft failed."""
        if self._draft_reply_fn is None:
            return None
        try:
            payload = await self._draft_reply_fn(
                number=number, cwd=self._cwd, course_id=self._course_id,
                target_comment_id=target)
        except Exception:  # noqa: BLE001 - surface as a failed on-demand draft
            return None
        payload = self._reconcile_thread_id(number, payload)
        self._drafts[(number, target)] = payload
        return payload

    def update_draft_body(self, number: int, new_body: str,
                          target: Optional[int] = None) -> Optional[DraftPayload]:
        """Replace a draft's body (e.g. after a manual edit), re-scanning the
        guardrail advisory. Returns the updated payload, or None if no draft."""
        draft = self._drafts.get((number, target))
        if draft is None:
            return None
        warnings = (self._rescan_fn(new_body, draft.project)
                    if self._rescan_fn is not None else draft.guardrail_warnings)
        updated = draft.model_copy(
            update={"body": new_body, "guardrail_warnings": warnings})
        self._drafts[(number, target)] = updated
        if self._persist_fn is not None:
            self._persist_fn(number, updated)
        return updated

    def _push_queue(self) -> None:
        # Fully-handled threads leave the rail: rejected (dismissed) and posted
        # (all drafts sent). Flagged threads stay, marked, for a human.
        items = [i for i in self._items.values()
                 if i.status not in ("dismissed", "posted")]
        self._emit(QueueUpdate(items=items))

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
        # Per-comment path: build the tree and draft a reply for each open
        # question. Falls back to the legacy single-draft path when the per-
        # comment machinery isn't wired (e.g. tests with only draft_fn).
        if self._fetch_tree_fn is not None and self._draft_reply_fn is not None:
            await self._autodraft_targets(number)
        else:
            await self._autodraft_single(number)

    def _reconcile_thread_id(self, number: int,
                             payload: DraftPayload) -> DraftPayload:
        # The watcher/seed event carries the authoritative GLOBAL thread id; the
        # agent's returned thread_id is an unguided LLM value, so reconcile it.
        item = self._items.get(number)
        if item is not None:
            return payload.model_copy(update={"thread_id": item.thread_id})
        return payload

    async def _autodraft_targets(self, number: int) -> None:
        from ed_bot.cockpit.thread_tree import actionable_targets
        self._emit(StatusUpdate(line=f"reading #{number}..."))
        await self._load_tree(number)
        op = self._trees.get(number)
        targets = actionable_targets(op) if op is not None else []
        if not targets:
            self._items[number] = self._items[number].model_copy(
                update={"draft_state": "none"})
            self._emit(StatusUpdate(line=f"#{number}: nothing to draft"))
            self._push_queue()
            return
        drafted = 0
        for t in targets:
            who = "the original post" if t.is_op else t.author
            self._emit(StatusUpdate(line=f"drafting #{number} → {who}..."))
            try:
                payload = await self._draft_reply_fn(
                    number=number, cwd=self._cwd, course_id=self._course_id,
                    target_comment_id=t.target_comment_id)
            except Exception:  # noqa: BLE001 - skip this target, keep the rest
                continue
            payload = self._reconcile_thread_id(number, payload)
            self._drafts[(number, t.target_comment_id)] = payload
            drafted += 1
        self._items[number] = self._items[number].model_copy(
            update={"draft_state": "ready" if drafted else "failed"})
        self._emit(StatusUpdate(line=f"#{number}: {drafted} draft(s) ready"))
        self._push_queue()

    async def _autodraft_single(self, number: int) -> None:
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
        payload = self._reconcile_thread_id(number, payload)
        self._drafts[(number, payload.target_comment_id)] = payload
        await self._load_tree(number)
        self._items[number] = self._items[number].model_copy(
            update={"draft_state": "ready"})
        self._emit(StatusUpdate(line=f"#{number} ready"))
        self._push_queue()

    async def _load_tree(self, number: int) -> None:
        """Fetch and store the thread's comment tree (best effort)."""
        if self._fetch_tree_fn is None:
            return
        try:
            self._trees[number] = await self._fetch_tree_fn(self._course_id, number)
        except Exception:  # noqa: BLE001 - the tree view is optional context
            pass

    async def _on_command(self, cmd: UserCommand):
        if cmd.intent == "open" and cmd.thread is not None:
            if cmd.target is not None:
                return self._drafts.get((cmd.thread, cmd.target))
            # Default open: the first draft for this thread (any target).
            for (num, _tgt), d in self._drafts.items():
                if num == cmd.thread:
                    return d
            return None
        if cmd.intent == "approve" and cmd.thread is not None:
            return await self._approve(cmd.thread, cmd.target)
        if cmd.intent == "reject" and cmd.thread is not None:
            self._reject(cmd.thread)
            return None
        if cmd.intent == "flag" and cmd.thread is not None:
            self._flag(cmd.thread)
            return None
        if cmd.intent == "skip" and cmd.thread is not None:
            self._emit(StatusUpdate(line=f"skipped #{cmd.thread}"))
            return None
        if cmd.intent == "check_forum":
            self._emit_queue_summary()
            return None
        if cmd.intent in ("freeform", "edit") and (
                self._chat_fn is not None or self._chat_edit_fn is not None):
            # "edit: shorten this" parses to intent=edit; route it through the
            # same edit-aware chat path as freeform so it isn't a silent no-op.
            await self._handle_freeform(cmd.text or "", cmd.thread, cmd.target)
            return None
        return None

    async def _handle_freeform(self, text: str,
                               active_thread: Optional[int] = None,
                               active_target: Optional[int] = None) -> None:
        # The lock serializes turns: turn N appends to history before turn N+1
        # reads it, so replies stay in order and each sees prior context.
        async with self._chat_lock:
            history = list(self._chat_history)
            self._chat_history.append(("you", text))
            self._emit(StatusUpdate(line="ed-bot is thinking..."))
            draft = (self._drafts.get((active_thread, active_target))
                     if active_thread is not None else None)
            try:
                if draft is not None and self._chat_edit_fn is not None:
                    reply = await self._chat_edit_turn(text, history,
                                                       active_thread, active_target,
                                                       draft)
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
                              number: int, target: Optional[int],
                              draft: DraftPayload) -> str:
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
            self._drafts[(number, target)] = updated
            if self._persist_fn is not None:
                self._persist_fn(number, updated)
            self._emit(updated)  # the app re-shows it in the draft viewer
            if not reply:
                reply = f"Updated the draft for #{number}."
        return reply

    def _reject(self, number: int) -> None:
        """Discard this thread: mark it dismissed so it drops out of the rail.
        No forum action."""
        item = self._items.get(number)
        if item is not None:
            self._items[number] = item.model_copy(update={"status": "dismissed"})
            self._emit(StatusUpdate(line=f"rejected #{number}"))
            self._push_queue()

    def _flag(self, number: int) -> None:
        """Leave this thread for a human: mark it flagged (stays in the rail,
        marked). No forum action."""
        item = self._items.get(number)
        if item is not None:
            self._items[number] = item.model_copy(update={"draft_state": "flagged"})
            self._emit(StatusUpdate(line=f"flagged #{number} for a human"))
            self._push_queue()

    def _emit_queue_summary(self) -> None:
        items = list(self._items.values())
        if not items:
            self._emit(ChatMessage(role="ed-bot", text="The queue is empty."))
            return
        parts = [f"#{i.number} ({i.draft_state})" for i in items]
        self._emit(ChatMessage(
            role="ed-bot",
            text=f"{len(items)} in queue: " + ", ".join(parts)))

    async def _approve(self, number: int,
                       target: Optional[int] = None) -> ActionResult:
        payload = self._drafts.get((number, target))
        if payload is None:
            return ActionResult(thread_id=0, ok=False, message="no draft to post")
        # Never post a placeholder: an empty body, or a "NEEDS HUMAN" flag the
        # agent returns when it is unsure or the thread is already handled.
        body = (payload.body or "").strip()
        if not body or body.upper().startswith("NEEDS HUMAN"):
            self._emit(StatusUpdate(
                line=f"#{number}: draft is NEEDS HUMAN / empty — not posting"))
            return ActionResult(
                thread_id=payload.thread_id, ok=False,
                message="draft is empty or flagged NEEDS HUMAN; not posting")
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
        if res.ok:
            # The draft is posted: drop it. When a thread has no drafts left to
            # post, mark it posted so it leaves the rail (a single-question
            # thread vanishes on post; a multi-question one stays until done).
            self._drafts.pop((number, target), None)
            item = self._items.get(number)
            if item is not None and not self.targets_with_drafts(number):
                self._items[number] = item.model_copy(update={"status": "posted"})
            self._emit(StatusUpdate(line=f"posted #{number}"))
            self._push_queue()
        return res
