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
from ed_bot.cockpit.agent import chat_reply as _agent_chat_reply
from ed_bot.cockpit.config import ed_working_dir, resolve_course_id
from ed_bot.cockpit.models import DraftPayload, WatcherEvent


def build_draft_fn(*, cwd: str, draft_thread=_agent_draft_thread):
    """The loop's draft_fn: always run the agent from the ed working dir so its
    tools (ed-api token, ~/.ed-bot) resolve, regardless of the number's cwd."""
    async def draft_fn(*, number: int, cwd: str = cwd, course_id: int) -> DraftPayload:
        return await draft_thread(number=number, cwd=cwd, course_id=course_id)
    return draft_fn


def build_chat_fn(*, cwd: str, chat_reply=_agent_chat_reply):
    """The loop's chat_fn: route freeform text to the agent from the ed dir,
    forwarding the conversation history so the chat has memory."""
    async def chat_fn(*, text: str, course_id: int,
                      history: list[tuple[str, str]] | None = None,
                      cwd: str = cwd) -> str:
        return await chat_reply(text=text, cwd=cwd, course_id=course_id,
                                history=history)
    return chat_fn


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

    cwd = str(ed_working_dir())
    course_id = resolve_course_id()
    draft_fn = build_draft_fn(cwd=cwd)
    chat_fn = build_chat_fn(cwd=cwd)

    bot_dir = pathlib.Path("~/.ed-bot").expanduser()
    bot_cfg = BotConfig.load(bot_dir)
    ed_bot_pkg = pathlib.Path(__file__).resolve().parents[1]  # ed_bot/
    watch_cfg = wconfig.load(bot_dir / "watch.yaml", ed_bot_dir=ed_bot_pkg)

    client = EdClient(region=bot_cfg.region)
    post_fn = build_post_fn(client=client)
    is_answered_fn = build_is_answered_fn(client=client)

    fetch_events = None
    if not args.no_watch:
        store = WatchAlertStore(bot_dir / "state" / "tracker.db")
        fetch_events = build_fetch_events(
            store=store, sound_files=watch_cfg.sounds)

    app = CockpitApp(cwd=cwd, course_id=course_id, draft_fn=draft_fn,
                     post_fn=post_fn, is_answered_fn=is_answered_fn,
                     fetch_events=fetch_events, chat_fn=chat_fn,
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
