"""Entry point: wire the real backends and run the cockpit.

Run with:        python -m ed_bot.cockpit
Demo a thread:   python -m ed_bot.cockpit --seed 222

``--seed N`` injects a WatcherEvent for thread N on startup so you can watch the
live agent draft it (the real watcher/poll wiring is a follow-up). The wiring
helpers are split out and injectable so they can be unit-tested without a live
app run or network."""
from __future__ import annotations

import argparse

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


def build_seed_event(number: int, course_id: int) -> WatcherEvent:
    """A minimal WatcherEvent to seed a demo draft for thread ``number``.

    Title/category aren't known without a fetch, so use placeholders — the agent
    fetches the real thread by number when it drafts."""
    return WatcherEvent(
        kind="new_thread", thread_id=number, number=number,
        title=f"(seeded thread #{number})", category="Project 1 | Martingale",
        url=f"https://edstem.org/us/courses/{course_id}/discussion/{number}",
    )


def parse_seed_numbers(raw: str | None) -> list[int]:
    """Parse a --seed value ('222' or '222,225,226') into a list of ints."""
    if not raw:
        return []
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def main() -> None:  # pragma: no cover - thin live wiring
    from ed_bot.cockpit.app import CockpitApp

    parser = argparse.ArgumentParser(prog="ed_bot.cockpit")
    parser.add_argument("--seed", type=str, default=None,
                        help="thread number(s) to seed on startup, comma-separated")
    args = parser.parse_args()

    cwd = str(ed_working_dir())
    course_id = resolve_course_id()
    draft_fn = build_draft_fn(cwd=cwd)
    chat_fn = build_chat_fn(cwd=cwd)

    # NOTE: post_fn / is_answered_fn / fetch_events wrap the sync ed-api client
    # via asyncio.to_thread in a follow-up; the app runs with auto-draft + chat
    # working against the agent now.
    app = CockpitApp(cwd=cwd, course_id=course_id, draft_fn=draft_fn,
                     post_fn=None, is_answered_fn=None, fetch_events=None,
                     chat_fn=chat_fn)

    seed_numbers = parse_seed_numbers(args.seed)
    if seed_numbers:
        async def _seed() -> None:
            for number in seed_numbers:
                await app.inject_event(build_seed_event(number, course_id))
        app.call_after_refresh(_seed)

    app.run()


if __name__ == "__main__":  # pragma: no cover
    main()
