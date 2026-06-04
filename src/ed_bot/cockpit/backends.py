"""Live EdStem backends for the cockpit: fetch_events, post_fn, is_answered_fn.

Each wraps the synchronous ed_api / watch code in asyncio.to_thread so the
Textual event loop never blocks. The builders take an injected client/store so
they can be unit-tested with fakes; __main__ constructs the real ones.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

from ed_bot.cockpit.models import ActionResult, WatcherEvent


def build_is_answered_fn(*, client: Any) -> Callable[[int], Awaitable[bool]]:
    """Async is_answered check: True when the thread already has an accepted
    answer. Used by the loop's staleness guard before posting a NEW answer."""
    async def is_answered(thread_id: int) -> bool:
        detail = await asyncio.to_thread(client.threads.get, thread_id)
        return bool(detail.is_answered)
    return is_answered


PostFn = Callable[..., Awaitable[ActionResult]]

_ACCEPT_WARN = "posted; could not accept (post-type thread). Resolve by hand."
_ACCEPT_UNCONFIRMED = (
    "posted, but EdStem did not confirm the thread was marked answered "
    "— please accept it by hand.")


def build_post_fn(*, client: Any, verify_attempts: int = 3,
                  verify_delay: float = 1.0,
                  sleep: "Callable[[float], None]" = time.sleep) -> PostFn:
    """Async post backend. Top-level answers post as --answer then accept;
    follow-ups post a nested reply and are never accepted.

    EdStem can return 200 to an accept call yet silently NOT mark the thread
    answered when the answer was just created (the cockpit posts and accepts
    back-to-back, unlike a human). So after accepting we re-fetch the thread to
    confirm it actually flipped to answered, retrying the accept a few times. If
    it still can't be confirmed we report accepted=False with an actionable
    warning instead of a false success."""
    def _is_answered(thread_id: int) -> "bool | None":
        """True/False from the live thread, or None if it can't be checked."""
        try:
            return bool(client.threads.get(thread_id).is_answered)
        except Exception:  # noqa: BLE001 - can't verify; caller trusts the 2xx
            return None

    def _post_answer(thread_id: int, body: str) -> ActionResult:
        comment = client.comments.post(thread_id, body, is_answer=True)
        try:
            client.comments.accept(comment.id)
        except Exception:  # noqa: BLE001 - post-type threads can't be accepted
            return ActionResult(thread_id=thread_id, ok=True, posted_id=comment.id,
                                accepted=False, message=_ACCEPT_WARN)
        for attempt in range(verify_attempts):
            answered = _is_answered(thread_id)
            if answered is None:
                # Unverifiable: trust the 2xx rather than hammer accept.
                return ActionResult(thread_id=thread_id, ok=True,
                                    posted_id=comment.id, accepted=True)
            if answered:
                return ActionResult(thread_id=thread_id, ok=True,
                                    posted_id=comment.id, accepted=True)
            if attempt < verify_attempts - 1:
                sleep(verify_delay)
                try:
                    client.comments.accept(comment.id)
                except Exception:  # noqa: BLE001 - give up cleanly on a hard error
                    break
        return ActionResult(thread_id=thread_id, ok=True, posted_id=comment.id,
                            accepted=False, message=_ACCEPT_UNCONFIRMED)

    def _post_reply(thread_id: int, body: str, target_comment_id: int) -> ActionResult:
        comment = client.comments.reply(target_comment_id, body)
        return ActionResult(thread_id=thread_id, ok=True, posted_id=comment.id,
                            accepted=False)

    def _post_sync(thread_id, body, post_kind, target_comment_id) -> ActionResult:
        if post_kind == "reply":
            if target_comment_id is None:
                return ActionResult(thread_id=thread_id, ok=False,
                                    message="reply requested but no target_comment_id")
            return _post_reply(thread_id, body, target_comment_id)
        return _post_answer(thread_id, body)

    async def post_fn(*, thread_id: int, number: int, body: str, post_kind: str,
                      target_comment_id: "int | None") -> ActionResult:
        try:
            return await asyncio.to_thread(
                _post_sync, thread_id, body, post_kind, target_comment_id)
        except Exception as e:  # noqa: BLE001 - surface as a failed action
            return ActionResult(thread_id=thread_id, ok=False, message=str(e))

    return post_fn


FetchEvents = Callable[[int], Awaitable[list[WatcherEvent]]]


def build_fetch_events(*, store: Any, sound_files: dict,
                       fetch: "Callable[[int], list[dict]] | None" = None,
                       play: "Callable[..., None] | None" = None,
                       poll: "Callable[..., None] | None" = None) -> FetchEvents:
    """Async fetch_events: one watch poll cycle per call, collecting emitted
    events as WatcherEvents. The cockpit owns the watch_alerts store while it
    runs (single source of truth; it subsumes /ed-watch for the session).

    fetch/play/poll are injectable for tests; defaults wire the real watch code.
    """
    if poll is None:
        from ed_bot.watch.poll import poll as _real_poll
        poll = _real_poll
    if play is None:
        from ed_bot.watch.sound import play as _real_play
        play = _real_play
    if fetch is None:
        from ed_bot.watch.cli import build_fetch
        fetch = build_fetch()  # NOTE: build_fetch takes NO arguments

    async def fetch_events(cid: int) -> list[WatcherEvent]:
        collected: list[WatcherEvent] = []

        def on_event(kind, **fields) -> None:
            collected.append(WatcherEvent(
                kind=kind,
                thread_id=fields["thread_id"],
                number=fields["number"],
                title=fields["title"],
                category=fields.get("category", ""),
                url=fields.get("url", ""),
            ))

        def _run() -> None:
            poll(course_id=cid, fetch=fetch, store=store, play=play,
                 sound_files=sound_files, on_event=on_event)

        await asyncio.to_thread(_run)
        return collected

    return fetch_events
