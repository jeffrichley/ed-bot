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
) -> None:
    """Run one poll. Side-effects: emit() on stdout, play() sound, store.record()."""
    threads = fetch(course_id)
    log.debug("Fetched %d threads for course %d", len(threads), course_id)

    for t in threads:
        decision: Decision = classify(t)
        kind = decision.kind
        thread_id = t["thread_id"]
        event_at = t["updated_at"]

        if not store.is_new_event(thread_id, kind, event_at):
            continue

        if kind == "silent":
            store.record(thread_id, "silent", event_at)
            continue

        # Re-emit guard: if we've previously alerted on this thread for the
        # same kind, only fire again if there's been non-staff activity since
        # our last alert. Staff replies = the thread is being handled.
        prev = store.get(thread_id)
        if prev is not None and prev["last_alert_kind"] == kind:
            if not t.get("has_non_staff_activity_since_alert", True):
                store.record(thread_id, "silent", event_at)
                continue

        # Actionable: play sound + emit JSON + record.
        play(kind, sound_files)
        emit(
            kind,
            thread_id=thread_id,
            number=t["number"],
            title=t["title"],
            category=t["category"],
            url=f"https://edstem.org/us/courses/{course_id}/discussion/{thread_id}",
        )
        store.record(thread_id, kind, event_at)
