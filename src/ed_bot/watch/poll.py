"""One poll cycle: fetch threads, classify, emit, play sound, record state."""
from __future__ import annotations

import logging
from typing import Callable

from ed_bot.watch.classify import Decision, classify
from ed_bot.watch.emit import emit
from ed_bot.watch.state import WatchAlertStore

log = logging.getLogger(__name__)

FetchFn = Callable[[int], list[dict]]
PlayFn = Callable[[str, dict], None]


def poll(
    *,
    course_id: int,
    fetch: FetchFn,
    store: WatchAlertStore,
    play: PlayFn,
    sound_files: dict,
    on_event: "Callable[..., None] | None" = None,
) -> None:
    """Run one poll. Side-effects: on_event() per actionable event (defaults to
    the stdout `emit`), play() sound, store.record()."""
    emit_event = on_event if on_event is not None else emit
    threads = fetch(course_id)
    log.debug("Fetched %d threads for course %d", len(threads), course_id)

    for t in threads:
        decision: Decision = classify(t)
        kind = decision.kind
        thread_id = t["thread_id"]
        event_at = t["updated_at"]
        reply_count = int(t.get("reply_count", 0) or 0)

        if not store.is_new_event(thread_id, kind, event_at):
            continue

        if kind == "silent":
            store.record(thread_id, "silent", event_at, reply_count)
            continue

        # Re-emit guards (only apply when we've already alerted on this thread
        # with the same kind — first-time alerts always fire).
        # NOTE: when silencing a re-emit, preserve the prior `kind` in the
        # stored row. Recording as "silent" would break the next poll's guard
        # check (`prev_kind == current_kind`) and the thread would re-emit.
        prev = store.get(thread_id)
        if prev is not None and prev["last_alert_kind"] == kind:
            prev_reply_count = int(prev.get("last_reply_count") or 0)
            # 1. Reply count hasn't grown — nothing meaningful happened.
            #    updated_at can tick for edits/votes/etc. without new replies.
            if reply_count <= prev_reply_count:
                store.record(thread_id, kind, event_at, reply_count)
                continue
            # 2. Replies grew, but only staff has touched the thread since
            #    our last alert — it's being handled, stay silent.
            if not t.get("has_non_staff_activity_since_alert", True):
                store.record(thread_id, kind, event_at, reply_count)
                continue

        # Actionable: play sound + emit JSON + record.
        play(kind, sound_files)
        emit_event(
            kind,
            thread_id=thread_id,
            number=t["number"],
            title=t["title"],
            category=t["category"],
            url=f"https://edstem.org/us/courses/{course_id}/discussion/{thread_id}",
        )
        store.record(thread_id, kind, event_at, reply_count)
