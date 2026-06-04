"""Entry point: wire the real backends and run the cockpit.

Run with:        python -m ed_bot.cockpit
Demo a thread:   python -m ed_bot.cockpit --seed 222

``--seed N`` injects a WatcherEvent for thread N on startup so you can watch the
live agent draft it (the real watcher/poll wiring is a follow-up). The wiring
helpers are split out and injectable so they can be unit-tested without a live
app run or network."""
from __future__ import annotations

import argparse
from datetime import datetime

from ed_bot.cockpit.agent import draft_thread as _agent_draft_thread
from ed_bot.cockpit.agent import draft_reply as _agent_draft_reply
from ed_bot.cockpit.agent import chat_reply as _agent_chat_reply
from ed_bot.cockpit.agent import chat_edit as _agent_chat_edit
from ed_bot.cockpit.config import ed_working_dir, resolve_course_id
from ed_bot.cockpit.models import DraftPayload, WatcherEvent


def build_draft_fn(*, cwd: str, draft_thread=_agent_draft_thread):
    """The loop's draft_fn: always run the agent from the ed working dir so its
    tools (ed-api token, ~/.ed-bot) resolve, regardless of the number's cwd."""
    async def draft_fn(*, number: int, cwd: str = cwd, course_id: int) -> DraftPayload:
        return await draft_thread(number=number, cwd=cwd, course_id=course_id)
    return draft_fn


def build_reply_fn(*, cwd: str, draft_reply=_agent_draft_reply):
    """The loop's per-comment draft fn: draft a reply to a specific comment (or
    the OP) from the ed working dir so the agent's tools resolve."""
    async def reply_fn(*, number: int, course_id: int, target_comment_id,
                       cwd: str = cwd) -> DraftPayload:
        return await draft_reply(number=number, cwd=cwd, course_id=course_id,
                                 target_comment_id=target_comment_id)
    return reply_fn


def build_chat_fn(*, cwd: str, chat_reply=_agent_chat_reply):
    """The loop's chat_fn: route freeform text to the agent from the ed dir,
    forwarding the conversation history so the chat has memory."""
    async def chat_fn(*, text: str, course_id: int,
                      history: list[tuple[str, str]] | None = None,
                      cwd: str = cwd) -> str:
        return await chat_reply(text=text, cwd=cwd, course_id=course_id,
                                history=history)
    return chat_fn


def build_chat_edit_fn(*, cwd: str, chat_edit=_agent_chat_edit):
    """The loop's chat_edit_fn: an edit-aware chat turn that can revise the
    active draft, run from the ed dir so the agent's tools resolve."""
    async def chat_edit_fn(*, text: str, course_id: int, thread_content: str,
                           current_body: str,
                           history: list[tuple[str, str]] | None = None,
                           cwd: str = cwd) -> dict:
        return await chat_edit(text=text, cwd=cwd, course_id=course_id,
                               history=history, thread_content=thread_content,
                               current_body=current_body)
    return chat_edit_fn


def build_rescan_fn():
    """The loop's rescan_fn: re-scan a revised body for advisory guardrail
    warnings, so the Never-Reveal advisory stays current after an edit."""
    from ed_bot.cockpit.agent import _guardrail_path_for
    from ed_bot.cockpit.guardrail_scan import scan_body

    def rescan(body: str, project) -> list[str]:
        return scan_body(body, _guardrail_path_for(project))
    return rescan


def build_fetch_meta(*, client):
    """Cheap staleness probe for the draft cache: a thread's reply_count +
    is_answered, fetched off the event loop."""
    import asyncio

    async def fetch_meta(course_id: int, number: int) -> dict:
        detail = await asyncio.to_thread(
            client.threads.get_by_number, course_id, number)
        return {"reply_count": detail.reply_count,
                "is_answered": detail.is_answered}
    return fetch_meta


def build_fetch_detail(*, client):
    """Fetch a thread's full detail (comments tree + users), off the loop."""
    import asyncio

    async def fetch_detail(course_id: int, number: int):
        return await asyncio.to_thread(
            client.threads.get_by_number, course_id, number)
    return fetch_detail


def build_fetch_tree_fn(*, client):
    """Fetch a thread and build its CommentNode tree, off the loop."""
    import asyncio
    from ed_bot.cockpit.thread_tree import build_comment_tree

    async def fetch_tree(course_id: int, number: int):
        detail = await asyncio.to_thread(
            client.threads.get_by_number, course_id, number)
        return build_comment_tree(detail)
    return fetch_tree


def build_tree_enriched_draft_fn(*, base, fetch_detail):
    """Wrap a draft fn so the draft's ``original_content`` is the deterministic,
    indented comment tree (with the targeted comment marked) instead of the
    agent's flat prose. Falls back to the agent's text on any fetch/parse error."""
    from ed_bot.cockpit.thread_tree import build_comment_tree, render_tree

    async def draft_fn(*, number: int, cwd: str, course_id: int):
        payload = await base(number=number, cwd=cwd, course_id=course_id)
        try:
            detail = await fetch_detail(course_id, number)
            op = build_comment_tree(detail)
            tree_text = render_tree(
                op, target_comment_id=payload.target_comment_id)
            payload = payload.model_copy(update={"original_content": tree_text})
        except Exception:  # noqa: BLE001 - keep the draft if the tree render fails
            pass
        return payload
    return draft_fn


def resolve_seed_thread_id(client, course_id: int, number: int) -> int:
    """Resolve a course-local thread number to its global EdStem thread id."""
    return client.threads.get_by_number(course_id, number).id


def build_seed_event(number: int, course_id: int, thread_id: int) -> WatcherEvent:
    """A minimal WatcherEvent to seed a demo draft for thread ``number``.

    ``thread_id`` is the resolved GLOBAL EdStem id (the loop reconciles drafts
    to it for routing). Title/category aren't known without a fetch, so use
    placeholders. The agent fetches the real thread by number when it drafts."""
    return WatcherEvent(
        kind="new_thread", thread_id=thread_id, number=number,
        title=f"(seeded thread #{number})", category="Project 1 | Martingale",
        url=f"https://edstem.org/us/courses/{course_id}/discussion/{number}",
    )


def parse_seed_numbers(raw: str | None) -> list[int]:
    """Parse a --seed value ('222' or '222,225,226') into a list of ints."""
    if not raw:
        return []
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def resolve_watch_interval(cfg, *, default: float = 120.0) -> float:
    """The poll interval (seconds) for the current time window, or `default`
    when no window matches or its interval is 'off'."""
    win = cfg.window_for(datetime.now())
    if win is None or win.interval_seconds is None:
        return default
    return float(win.interval_seconds)


def main() -> None:  # pragma: no cover - thin live wiring
    import pathlib
    from ed_api import EdClient
    from ed_bot.config import BotConfig
    from ed_bot.watch import config as wconfig
    from ed_bot.watch.state import WatchAlertStore
    from ed_bot.cockpit.app import CockpitApp
    from ed_bot.cockpit.backends import (
        build_fetch_events, build_post_fn, build_is_answered_fn,
    )

    parser = argparse.ArgumentParser(prog="ed_bot.cockpit")
    parser.add_argument("--seed", type=str, default=None,
                        help="thread number(s) to seed on startup, comma-separated")
    parser.add_argument("--no-watch", action="store_true",
                        help="don't poll the live forum (seed-only)")
    args = parser.parse_args()

    from ed_bot.cockpit.draft_cache import (
        build_cached_draft_fn, build_cached_reply_fn, update_payload,
    )

    cwd = str(ed_working_dir())
    course_id = resolve_course_id()
    chat_fn = build_chat_fn(cwd=cwd)
    chat_edit_fn = build_chat_edit_fn(cwd=cwd)
    rescan_fn = build_rescan_fn()

    bot_dir = pathlib.Path("~/.ed-bot").expanduser()
    bot_cfg = BotConfig.load(bot_dir)
    ed_bot_pkg = pathlib.Path(__file__).resolve().parents[1]  # ed_bot/
    watch_cfg = wconfig.load(bot_dir / "watch.yaml", ed_bot_dir=ed_bot_pkg)

    client = EdClient(region=bot_cfg.region)
    post_fn = build_post_fn(client=client)
    is_answered_fn = build_is_answered_fn(client=client)

    # Draft pipeline: agent draft -> enrich original_content with the real,
    # indented comment tree -> cache (reuse while the thread is unchanged).
    cache_dir = bot_dir / "cockpit-drafts"
    inner_draft = build_tree_enriched_draft_fn(
        base=build_draft_fn(cwd=cwd),
        fetch_detail=build_fetch_detail(client=client))
    draft_fn = build_cached_draft_fn(
        inner=inner_draft,
        fetch_meta=build_fetch_meta(client=client), cache_dir=cache_dir)

    def persist_fn(number: int, payload) -> None:
        update_payload(cache_dir, course_id, number, payload)

    fetch_tree_fn = build_fetch_tree_fn(client=client)

    # Per-comment drafting: draft a reply to each open question, cached per
    # target so re-opening an unchanged thread is instant.
    draft_reply_fn = build_cached_reply_fn(
        inner=build_reply_fn(cwd=cwd),
        fetch_meta=build_fetch_meta(client=client), cache_dir=cache_dir)

    # A distinct, lower completion chime when a draft finishes (separate from the
    # watcher's new-thread ping). Best-effort: silent if no draft_ready sound is
    # configured or no speaker is available.
    from ed_bot.watch.sound import play as play_sound

    def on_draft_ready(number: int) -> None:
        if "draft_ready" in watch_cfg.sounds:
            play_sound("draft_ready", watch_cfg.sounds)  # type: ignore[arg-type]

    fetch_events = None
    if not args.no_watch:
        store = WatchAlertStore(bot_dir / "state" / "tracker.db")
        fetch_events = build_fetch_events(
            store=store, sound_files=watch_cfg.sounds)

    app = CockpitApp(cwd=cwd, course_id=course_id, draft_fn=draft_fn,
                     post_fn=post_fn, is_answered_fn=is_answered_fn,
                     fetch_events=fetch_events, chat_fn=chat_fn,
                     chat_edit_fn=chat_edit_fn, rescan_fn=rescan_fn,
                     persist_fn=persist_fn, fetch_tree_fn=fetch_tree_fn,
                     draft_reply_fn=draft_reply_fn, on_draft_ready=on_draft_ready,
                     watch_interval=resolve_watch_interval(watch_cfg))

    seed_numbers = parse_seed_numbers(args.seed)
    if seed_numbers:
        def _seed() -> None:
            # draft_event is a @work worker (non-blocking): the rows render
            # immediately and each draft runs in the background, so the UI and
            # input stay responsive during the live SDK calls.
            for number in seed_numbers:
                tid = resolve_seed_thread_id(client, course_id, number)
                app.draft_event(build_seed_event(number, course_id, tid))
        app.call_after_refresh(_seed)

    app.run()


if __name__ == "__main__":  # pragma: no cover
    main()
