"""Entry point: wire the real backends and run the cockpit.

Run with:  python -m ed_bot.cockpit

The wiring helpers are split out and injectable so they can be unit-tested
without a live app run or network."""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from ed_bot.cockpit.agent import draft_thread as _agent_draft_thread
from ed_bot.cockpit.config import ed_working_dir, resolve_course_id
from ed_bot.cockpit.models import DraftPayload


def build_draft_fn(*, cwd: str, draft_thread=_agent_draft_thread):
    """The loop's draft_fn: always run the agent from the ed working dir so its
    tools (ed-api token, ~/.ed-bot) resolve, regardless of the number's cwd."""
    async def draft_fn(*, number: int, cwd: str = cwd, course_id: int) -> DraftPayload:
        return await draft_thread(number=number, cwd=cwd, course_id=course_id)
    return draft_fn


def main() -> None:  # pragma: no cover - thin live wiring
    from ed_bot.cockpit.app import CockpitApp

    cwd = str(ed_working_dir())
    course_id = resolve_course_id()
    draft_fn = build_draft_fn(cwd=cwd)

    # NOTE: post_fn / is_answered_fn / fetch_events wrap the sync ed-api client
    # via asyncio.to_thread in a follow-up; the app runs with auto-draft + chat
    # working against the agent now.
    app = CockpitApp(cwd=cwd, course_id=course_id, draft_fn=draft_fn,
                     post_fn=None, is_answered_fn=None, fetch_events=None)
    app.run()


if __name__ == "__main__":  # pragma: no cover
    main()
