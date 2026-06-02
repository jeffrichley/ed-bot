# Cockpit Live Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the cockpit's three stub hooks (`fetch_events`, `post_fn`, `is_answered_fn`) to live EdStem backends so the cockpit watches the forum (with sound), auto-drafts, and posts approved answers in one asyncio process.

**Architecture:** Reuse the existing `ed_bot.watch` poll (dedup + sound) by making its event emission pluggable; add a `cockpit/backends.py` that wraps the synchronous `ed_api`/watch code in `asyncio.to_thread`; fix the loop's staleness guard to apply only to top-level answers; start the watcher from the app on mount; wire real backends in `__main__`.

**Tech Stack:** Python 3.11, asyncio, Textual, `ed_api` SDK, `ed_bot.watch`, pytest (+ `pytest.mark.asyncio`).

**Spec:** `docs/superpowers/specs/2026-06-01-cockpit-live-wiring-design.md`

**Branch:** `feat/cockpit-live-wiring` (already created and checked out).

---

## File Structure

- Modify `src/ed_bot/watch/poll.py` — add `on_event` callback param (default = stdout `emit`).
- Modify `src/ed_bot/watch/cli.py` — extract `build_fetch(course_id)` from `_build_poll_fn`.
- Create `src/ed_bot/cockpit/backends.py` — `build_is_answered_fn`, `build_post_fn`, `build_fetch_events`.
- Modify `src/ed_bot/cockpit/loop.py` — guard only on `post_kind=="answer"`, forward `thread_id`.
- Modify `src/ed_bot/cockpit/app.py` — start the watcher on mount; store `course_id` + interval.
- Modify `src/ed_bot/cockpit/__main__.py` — build & pass the real backends; `--no-watch`; interval resolver.
- Modify `CLAUDE.md` — note the cockpit subsumes `/ed-watch` for its session.
- Tests: `tests/watch/test_poll.py` (extend), `tests/cockpit/test_backends.py` (new), `tests/cockpit/test_loop_post.py` (extend), `tests/cockpit/test_app_watcher.py` (new), `tests/cockpit/test_main_wiring.py` (extend).

---

## Task 1: Make `watch/poll.py` emission pluggable

**Files:**
- Modify: `src/ed_bot/watch/poll.py`
- Test: `tests/watch/test_poll.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/watch/test_poll.py`:

```python
def test_poll_calls_on_event_instead_of_stdout(capsys):
    """A custom on_event receives the event fields; stdout stays quiet."""
    from ed_bot.watch.poll import poll
    from ed_bot.watch.state import WatchAlertStore

    captured = []

    def fetch(cid):
        return [{
            "thread_id": 555, "number": 12, "title": "Bollinger help",
            "category": "Project 6 | Indicators", "updated_at": "2026-06-01T00:00:00+00:00",
            "reply_count": 0, "is_answered": False,
        }]

    store = WatchAlertStore(":memory:")
    poll(course_id=99, fetch=fetch, store=store, play=lambda *a, **k: None,
         sound_files={}, on_event=lambda kind, **f: captured.append((kind, f)))
    store.close()

    assert len(captured) == 1
    kind, fields = captured[0]
    assert kind == "new_thread"
    assert fields["thread_id"] == 555
    assert fields["number"] == 12
    assert fields["title"] == "Bollinger help"
    # Nothing was written to stdout because on_event was provided.
    assert capsys.readouterr().out == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/watch/test_poll.py::test_poll_calls_on_event_instead_of_stdout -v`
Expected: FAIL — `poll()` got an unexpected keyword argument `on_event`.

- [ ] **Step 3: Implement**

In `src/ed_bot/watch/poll.py`, import is already `from ed_bot.watch.emit import emit`. Change the signature and the emit call:

```python
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
```

Then replace the existing `emit(` call inside the actionable branch with `emit_event(`:

```python
        # Actionable: play sound + emit + record.
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
```

(Keep the top-of-file `from ed_bot.watch.emit import emit` import; `Callable` is already imported via `from typing import Callable`.)

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/Scripts/python.exe -m pytest tests/watch/test_poll.py -v`
Expected: PASS (new test + all existing poll tests, which use the default `emit` path).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/watch/poll.py tests/watch/test_poll.py
git commit -m "feat(watch): make poll event emission pluggable via on_event"
```

---

## Task 2: Extract `build_fetch(course_id)` in `watch/cli.py`

**Files:**
- Modify: `src/ed_bot/watch/cli.py`
- Test: `tests/watch/test_cli_build_fetch.py` (new)

The `fetch` closure currently lives inside `_build_poll_fn`. Extract it to a module-level `build_fetch(course_id) -> FetchFn` so the cockpit can drive `run_poll` with its own `on_event`. `_build_poll_fn` then calls `build_fetch`.

- [ ] **Step 1: Write the failing test**

Create `tests/watch/test_cli_build_fetch.py`:

```python
def test_build_fetch_is_importable_and_returns_callable():
    from ed_bot.watch.cli import build_fetch
    fetch = build_fetch(12345)
    assert callable(fetch)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/watch/test_cli_build_fetch.py -v`
Expected: FAIL — `cannot import name 'build_fetch'`.

- [ ] **Step 3: Implement**

In `src/ed_bot/watch/cli.py`, lift the inner `fetch` closure (and its helpers `_tracker_lookup`, `_has_student_followup`, the `EdClient` construction, the `sqlite3` import) out of `_build_poll_fn` into a new module-level function:

```python
def build_fetch(course_id: int) -> "Callable[[int], list[dict]]":
    """Build the tracker-cross-referencing fetch closure used by the watch poll.

    Shared by the standalone watcher (`_build_poll_fn`) and the cockpit's
    `fetch_events` backend so the dedup / follow-up / escalation-handled logic
    has a single source of truth.
    """
    from ed_api import EdClient
    import sqlite3
    client = EdClient()

    def _tracker_lookup(conn, thread_id):
        # ... (move body verbatim from _build_poll_fn) ...
        row = conn.execute(
            "SELECT our_answer_id, reply_count_seen FROM threads WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
        if row is None:
            return None, 0
        return row[0], row[1] or 0

    def _has_student_followup(detail, our_answer_id):
        # ... (move body verbatim) ...
        our_answer_time = None
        for c in _iter_comments(detail):
            if getattr(c, "id", None) == our_answer_id:
                our_answer_time = _created_of(c)
                break
        if our_answer_time is None:
            return False
        for c in _iter_comments(detail):
            if getattr(c, "id", None) == our_answer_id:
                continue
            created = _created_of(c)
            if not _comment_is_staff(c) and created is not None and created > our_answer_time:
                return True
        return False

    def fetch(cid: int) -> list[dict]:
        # ... (move the existing fetch body verbatim) ...
        ...

    return fetch
```

Then simplify `_build_poll_fn` to use it:

```python
def _build_poll_fn(course_id: int, store: WatchAlertStore, sound_files: dict) -> Callable[[], None]:
    """Returns a no-arg callable suitable for the scheduler."""
    fetch = build_fetch(course_id)

    def once() -> None:
        run_poll(course_id=course_id, fetch=fetch, store=store,
                 play=play, sound_files=sound_files)

    return once
```

Keep `_iter_comments`, `_comment_is_staff`, `_created_of`, `_as_datetime`, `_has_non_staff_activity_since` where they are (module-level already). `build_fetch`'s `fetch` body references them unchanged.

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/Scripts/python.exe -m pytest tests/watch/ -v`
Expected: PASS (new import test + all existing watch tests; `_build_poll_fn` behavior is unchanged).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/watch/cli.py tests/watch/test_cli_build_fetch.py
git commit -m "refactor(watch): extract build_fetch for reuse by the cockpit"
```

---

## Task 3: `cockpit/backends.py` — `build_is_answered_fn`

**Files:**
- Create: `src/ed_bot/cockpit/backends.py`
- Test: `tests/cockpit/test_backends.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/cockpit/test_backends.py`:

```python
import pytest

pytestmark = pytest.mark.asyncio


class _FakeThreadDetail:
    def __init__(self, is_answered):
        self.is_answered = is_answered


class _FakeThreads:
    def __init__(self, detail):
        self._detail = detail
        self.got = []

    def get(self, thread_id):
        self.got.append(thread_id)
        return self._detail


class _FakeClient:
    def __init__(self, *, is_answered=False):
        self.threads = _FakeThreads(_FakeThreadDetail(is_answered))
        self.comments = None
        self.closed = False

    def close(self):
        self.closed = True


async def test_is_answered_fn_returns_thread_flag():
    from ed_bot.cockpit.backends import build_is_answered_fn
    client = _FakeClient(is_answered=True)
    is_answered = build_is_answered_fn(client=client)
    assert await is_answered(99887) is True
    assert client.threads.got == [99887]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_backends.py::test_is_answered_fn_returns_thread_flag -v`
Expected: FAIL — module `ed_bot.cockpit.backends` does not exist.

- [ ] **Step 3: Implement**

Create `src/ed_bot/cockpit/backends.py`:

```python
"""Live EdStem backends for the cockpit: fetch_events, post_fn, is_answered_fn.

Each wraps the synchronous ed_api / watch code in asyncio.to_thread so the
Textual event loop never blocks. The builders take an injected client/store so
they can be unit-tested with fakes; __main__ constructs the real ones.
"""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from ed_bot.cockpit.models import ActionResult, WatcherEvent


def build_is_answered_fn(*, client: Any) -> Callable[[int], Awaitable[bool]]:
    """Async is_answered check: True when the thread already has an accepted
    answer. Used by the loop's staleness guard before posting a NEW answer."""
    async def is_answered(thread_id: int) -> bool:
        detail = await asyncio.to_thread(client.threads.get, thread_id)
        return bool(detail.is_answered)
    return is_answered
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_backends.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/backends.py tests/cockpit/test_backends.py
git commit -m "feat(cockpit): add is_answered backend"
```

---

## Task 4: `cockpit/backends.py` — `build_post_fn`

**Files:**
- Modify: `src/ed_bot/cockpit/backends.py`
- Test: `tests/cockpit/test_backends.py`

Behavior: `post_kind="answer"` posts as answer then tries to accept (accept failure → `ok=True, accepted=False`, warning); `post_kind="reply"` posts a nested reply, no accept; any network exception → `ok=False`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/cockpit/test_backends.py`:

```python
class _FakeComment:
    def __init__(self, id):
        self.id = id


class _FakeComments:
    def __init__(self, *, accept_raises=False):
        self.posted = []
        self.replied = []
        self.accepted = []
        self._accept_raises = accept_raises

    def post(self, thread_id, content, is_answer=False):
        self.posted.append((thread_id, content, is_answer))
        return _FakeComment(id=4242)

    def reply(self, comment_id, content):
        self.replied.append((comment_id, content))
        return _FakeComment(id=7777)

    def accept(self, comment_id):
        self.accepted.append(comment_id)
        if self._accept_raises:
            raise RuntimeError("Invalid answer ancestor")


class _PostClient:
    def __init__(self, *, accept_raises=False):
        self.comments = _FakeComments(accept_raises=accept_raises)


async def test_post_answer_posts_and_accepts():
    from ed_bot.cockpit.backends import build_post_fn
    client = _PostClient()
    post = build_post_fn(client=client)
    res = await post(thread_id=500, number=10, body="Here's the answer.",
                     post_kind="answer", target_comment_id=None)
    assert res.ok is True
    assert res.accepted is True
    assert res.posted_id == 4242
    assert client.comments.posted == [(500, "Here's the answer.", True)]
    assert client.comments.accepted == [4242]


async def test_post_answer_warns_when_accept_fails():
    from ed_bot.cockpit.backends import build_post_fn
    client = _PostClient(accept_raises=True)
    post = build_post_fn(client=client)
    res = await post(thread_id=500, number=10, body="Answer for a post-type thread.",
                     post_kind="answer", target_comment_id=None)
    # Posting still counts as success; accept failure is a non-fatal warning.
    assert res.ok is True
    assert res.accepted is False
    assert res.posted_id == 4242
    assert "accept" in res.message.lower()


async def test_post_reply_does_not_accept():
    from ed_bot.cockpit.backends import build_post_fn
    client = _PostClient()
    post = build_post_fn(client=client)
    res = await post(thread_id=500, number=10, body="Follow-up reply.",
                     post_kind="reply", target_comment_id=909)
    assert res.ok is True
    assert res.posted_id == 7777
    assert client.comments.replied == [(909, "Follow-up reply.")]
    assert client.comments.accepted == []  # replies are never accepted


async def test_post_returns_not_ok_on_network_error():
    from ed_bot.cockpit.backends import build_post_fn

    class _BoomComments:
        def post(self, *a, **k):
            raise RuntimeError("503 from EdStem")

    class _BoomClient:
        comments = _BoomComments()

    post = build_post_fn(client=_BoomClient())
    res = await post(thread_id=1, number=1, body="x", post_kind="answer",
                     target_comment_id=None)
    assert res.ok is False
    assert "503" in res.message
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_backends.py -k post -v`
Expected: FAIL — `build_post_fn` does not exist.

- [ ] **Step 3: Implement**

Add to `src/ed_bot/cockpit/backends.py`:

```python
PostFn = Callable[..., Awaitable[ActionResult]]

_ACCEPT_WARN = "posted; could not accept (post-type thread) — resolve by hand"


def build_post_fn(*, client: Any) -> PostFn:
    """Async post backend. Top-level answers post as --answer then try to
    accept (accept failure is a non-fatal warning); follow-ups post a nested
    reply and are never accepted."""
    def _post_answer(thread_id: int, body: str) -> ActionResult:
        comment = client.comments.post(thread_id, body, is_answer=True)
        try:
            client.comments.accept(comment.id)
        except Exception:  # noqa: BLE001 - post-type threads can't be accepted
            return ActionResult(thread_id=thread_id, ok=True, posted_id=comment.id,
                                accepted=False, message=_ACCEPT_WARN)
        return ActionResult(thread_id=thread_id, ok=True, posted_id=comment.id,
                            accepted=True)

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_backends.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/backends.py tests/cockpit/test_backends.py
git commit -m "feat(cockpit): add post backend (answer+accept, warn on post-type, nested reply)"
```

---

## Task 5: `cockpit/backends.py` — `build_fetch_events`

**Files:**
- Modify: `src/ed_bot/cockpit/backends.py`
- Test: `tests/cockpit/test_backends.py`

`fetch_events(cid)` runs one `run_poll` cycle (with the shared `fetch` + an event collector) inside `asyncio.to_thread`, returning the collected `WatcherEvent`s. To keep the test hermetic, the builder takes injected `poll`, `fetch`, `store`, `play`, `sound_files`.

- [ ] **Step 1: Write the failing test**

Add to `tests/cockpit/test_backends.py`:

```python
async def test_fetch_events_collects_watcher_events():
    from ed_bot.cockpit.backends import build_fetch_events
    from ed_bot.cockpit.models import WatcherEvent

    # A fake poll that drives on_event the way the real run_poll does.
    def fake_poll(*, course_id, fetch, store, play, sound_files, on_event):
        on_event("new_thread", thread_id=321, number=7, title="RF indicators",
                 category="Project 8 | Random Forest",
                 url="https://edstem.org/us/courses/1/discussion/321")

    events = build_fetch_events(course_id=1, store=object(), sound_files={},
                                fetch=lambda cid: [], play=lambda *a, **k: None,
                                poll=fake_poll)
    out = await events(1)
    assert len(out) == 1
    ev = out[0]
    assert isinstance(ev, WatcherEvent)
    assert ev.kind == "new_thread"
    assert ev.thread_id == 321
    assert ev.number == 7
    assert ev.title == "RF indicators"


async def test_fetch_events_offloads_to_thread():
    """The poll runs off the event loop (in a worker thread)."""
    import threading
    from ed_bot.cockpit.backends import build_fetch_events

    main_thread = threading.current_thread().ident
    seen = {}

    def fake_poll(*, course_id, fetch, store, play, sound_files, on_event):
        seen["thread"] = threading.current_thread().ident

    events = build_fetch_events(course_id=1, store=object(), sound_files={},
                                fetch=lambda cid: [], play=lambda *a, **k: None,
                                poll=fake_poll)
    await events(1)
    assert seen["thread"] != main_thread
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_backends.py -k fetch_events -v`
Expected: FAIL — `build_fetch_events` does not exist.

- [ ] **Step 3: Implement**

Add to `src/ed_bot/cockpit/backends.py`:

```python
FetchEvents = Callable[[int], Awaitable[list[WatcherEvent]]]


def build_fetch_events(*, course_id: int, store: Any, sound_files: dict,
                       fetch: "Callable[[int], list[dict]] | None" = None,
                       play: "Callable[..., None] | None" = None,
                       poll: "Callable[..., None] | None" = None) -> FetchEvents:
    """Async fetch_events: one watch poll cycle per call, collecting emitted
    events as WatcherEvents. The cockpit owns the watch_alerts store while it
    runs (single source of truth; it subsumes /ed-watch for the session).

    fetch/play/poll are injectable for tests; defaults wire the real watch code.
    """
    if poll is None:
        from ed_bot.watch.poll import poll as poll  # noqa: PLW0127
    if play is None:
        from ed_bot.watch.sound import play as play  # noqa: PLW0127
    if fetch is None:
        from ed_bot.watch.cli import build_fetch
        fetch = build_fetch(course_id)

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_backends.py -v`
Expected: PASS (all backend tests).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/backends.py tests/cockpit/test_backends.py
git commit -m "feat(cockpit): add fetch_events backend collecting watch poll events"
```

---

## Task 6: `cockpit/loop.py` — guard only on answers, forward `thread_id`

**Files:**
- Modify: `src/ed_bot/cockpit/loop.py`
- Test: `tests/cockpit/test_loop_post.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/cockpit/test_loop_post.py` (keep existing tests; they will be updated in Step 3 where signatures changed):

```python
@pytest.mark.asyncio
async def test_reply_not_blocked_by_is_answered():
    """A follow-up reply legitimately targets an already-answered thread, so the
    staleness guard must not skip it."""
    from ed_bot.cockpit.loop import CockpitLoop
    from ed_bot.cockpit.models import DraftPayload, UserCommand, ActionResult

    posts = []

    async def post_fn(*, thread_id, number, body, post_kind, target_comment_id):
        posts.append((thread_id, post_kind, target_comment_id))
        return ActionResult(thread_id=thread_id, ok=True, posted_id=1)

    async def is_answered_fn(thread_id):
        return True  # thread already has an accepted answer

    loop = CockpitLoop(cwd=".", course_id=1, draft_fn=None, emit=lambda x: None,
                       post_fn=post_fn, is_answered_fn=is_answered_fn)
    loop._drafts[207] = DraftPayload(
        thread_id=8100207, number=207, question="q", body="reply body",
        post_kind="reply", target_comment_id=909)

    res = await loop.handle(UserCommand(intent="approve", thread=207))
    assert res.ok is True
    assert posts == [(8100207, "reply", 909)]


@pytest.mark.asyncio
async def test_answer_forwards_thread_id_to_post_fn():
    from ed_bot.cockpit.loop import CockpitLoop
    from ed_bot.cockpit.models import DraftPayload, UserCommand, ActionResult

    seen = {}

    async def post_fn(*, thread_id, number, body, post_kind, target_comment_id):
        seen["thread_id"] = thread_id
        return ActionResult(thread_id=thread_id, ok=True, posted_id=1)

    async def is_answered_fn(thread_id):
        seen["checked"] = thread_id
        return False

    loop = CockpitLoop(cwd=".", course_id=1, draft_fn=None, emit=lambda x: None,
                       post_fn=post_fn, is_answered_fn=is_answered_fn)
    loop._drafts[207] = DraftPayload(
        thread_id=8100207, number=207, question="q", body="answer body",
        post_kind="answer")

    await loop.handle(UserCommand(intent="approve", thread=207))
    assert seen["thread_id"] == 8100207
    assert seen["checked"] == 8100207
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_loop_post.py -k "reply_not_blocked or forwards_thread_id" -v`
Expected: FAIL — the guard currently calls `is_answered_fn(number)` and blocks replies / passes the wrong id.

- [ ] **Step 3: Implement**

In `src/ed_bot/cockpit/loop.py`, update the type aliases:

```python
PostFn = Callable[..., Awaitable[ActionResult]]
IsAnsweredFn = Callable[[int], Awaitable[bool]]  # now called with thread_id
```

Replace `_approve`:

```python
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
        if res.ok:
            self._items[number] = self._items[number].model_copy(
                update={"status": "posted"})
            self._emit(StatusUpdate(line=f"posted #{number}"))
            self._push_queue()
        return res
```

Then update the EXISTING tests in `tests/cockpit/test_loop_post.py` whose fakes use the old signatures:
- `test_approve_posts_and_marks_posted`: the fake `post_fn` must accept a `thread_id` kwarg (add `thread_id` to its parameter list). Ensure the seeded `DraftPayload` has a `thread_id` set.
- `test_approve_skips_post_when_already_answered`: the fake `is_answered_fn` is now called with `thread_id` (the payload's), and the draft must be `post_kind="answer"` (default) with a known `thread_id`. Assert accordingly.

(Read those two tests and adjust their fake signatures/assertions to match the new `thread_id`-based calls.)

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_loop_post.py -v`
Expected: PASS (new + adjusted existing).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/loop.py tests/cockpit/test_loop_post.py
git commit -m "fix(cockpit): staleness guard only blocks answers; forward thread_id to backends"
```

---

## Task 7: `cockpit/app.py` — start the watcher on mount

**Files:**
- Modify: `src/ed_bot/cockpit/app.py`
- Test: `tests/cockpit/test_app_watcher.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/cockpit/test_app_watcher.py`:

```python
import pytest

pytestmark = pytest.mark.asyncio


async def test_app_watcher_drafts_polled_event():
    """With a fetch_events that yields one event, the app's watcher creates a
    queue item and drafts it."""
    from ed_bot.cockpit.app import CockpitApp
    from ed_bot.cockpit.models import DraftPayload, WatcherEvent

    async def fetch_events(cid):
        return [WatcherEvent(kind="new_thread", thread_id=900, number=42,
                             title="Bollinger help",
                             category="Project 6 | Indicators",
                             url="https://edstem.org/x")]

    async def draft_fn(*, number, cwd, course_id):
        return DraftPayload(thread_id=900, number=number, question="q",
                            body="drafted body", post_kind="answer")

    app = CockpitApp(cwd=".", course_id=1, draft_fn=draft_fn,
                     fetch_events=fetch_events, watch_interval=0.05)
    async with app.run_test() as pilot:
        # Let the producer poll once and the consumer draft it.
        for _ in range(20):
            await pilot.pause()
            if app.loop.queue_item(42) is not None and app.loop.draft(42) is not None:
                break
        assert app.loop.queue_item(42) is not None
        assert app.loop.draft(42).body == "drafted body"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_app_watcher.py -v`
Expected: FAIL — `CockpitApp.__init__` has no `watch_interval`; the watcher never starts.

- [ ] **Step 3: Implement**

In `src/ed_bot/cockpit/app.py`:

Add imports at the top:

```python
import asyncio
from ed_bot.cockpit.watcher import watch_loop
```

Extend `__init__` to store `course_id`, the interval, and watcher state:

```python
    def __init__(self, *, cwd: str, course_id: int, draft_fn,
                 post_fn=None, is_answered_fn=None, fetch_events=None,
                 chat_fn=None, watch_interval: float = 120.0) -> None:
        super().__init__()
        self._fetch_events = fetch_events
        self._course_id = course_id
        self._watch_interval = watch_interval
        self._watch_stop: "asyncio.Event | None" = None
        self._watch_queue: "asyncio.Queue | None" = None
        self._active_thread: Optional[int] = None
        self.loop = CockpitLoop(
            cwd=cwd, course_id=course_id, draft_fn=draft_fn,
            emit=self._emit, post_fn=post_fn, is_answered_fn=is_answered_fn,
            chat_fn=chat_fn,
        )
```

Start the watcher at the end of `on_mount`:

```python
    def on_mount(self) -> None:
        self.query_one(QueueRail).show([])
        self.query_one(DraftViewer).show(None)
        self.query_one(StatusBar).show("ready")
        self.query_one("#chat", Input).focus()
        if self._fetch_events is not None:
            self._watch_stop = asyncio.Event()
            self._watch_queue = asyncio.Queue()
            self._run_watch_producer()
            self._run_watch_consumer()
```

Add the two workers and a clean stop:

```python
    @work(group="watch")
    async def _run_watch_producer(self) -> None:
        """Poll the forum on an interval, putting events on the watch queue."""
        await watch_loop(
            course_id=self._course_id, queue=self._watch_queue,
            fetch_events=self._fetch_events,
            interval_seconds=self._watch_interval, stop=self._watch_stop,
        )

    @work(group="watch")
    async def _run_watch_consumer(self) -> None:
        """Drain polled events and draft each on the non-blocking draft worker."""
        assert self._watch_queue is not None and self._watch_stop is not None
        while not self._watch_stop.is_set():
            ev = await self._watch_queue.get()
            self.draft_event(ev)

    def on_unmount(self) -> None:
        if self._watch_stop is not None:
            self._watch_stop.set()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_app_watcher.py -v`
Expected: PASS.

- [ ] **Step 5: Run the whole cockpit + watch suite**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit tests/watch -q`
Expected: PASS (no regressions).

- [ ] **Step 6: Commit**

```bash
git add src/ed_bot/cockpit/app.py tests/cockpit/test_app_watcher.py
git commit -m "feat(cockpit): start the live watcher on mount (producer + consumer workers)"
```

---

## Task 8: `cockpit/__main__.py` — wire real backends, `--no-watch`, interval

**Files:**
- Modify: `src/ed_bot/cockpit/__main__.py`
- Test: `tests/cockpit/test_main_wiring.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/cockpit/test_main_wiring.py`:

```python
def test_resolve_watch_interval_defaults_when_no_window():
    from ed_bot.cockpit.__main__ import resolve_watch_interval
    from ed_bot.watch.config import WatchConfig
    cfg = WatchConfig(course_id=1, windows=[], sounds={})
    # No matching window -> the documented default.
    assert resolve_watch_interval(cfg) == 120.0


def test_resolve_watch_interval_uses_window_interval():
    from ed_bot.cockpit.__main__ import resolve_watch_interval
    from ed_bot.watch.config import WatchConfig, Window
    win = Window(days=["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                 start_hour=0, start_minute=0, end_hour=23, end_minute=59,
                 interval_seconds=300)
    cfg = WatchConfig(course_id=1, windows=[win], sounds={})
    assert resolve_watch_interval(cfg) == 300.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_main_wiring.py -k resolve_watch_interval -v`
Expected: FAIL — `resolve_watch_interval` does not exist.

- [ ] **Step 3: Implement**

In `src/ed_bot/cockpit/__main__.py`, add a datetime import and the resolver:

```python
from datetime import datetime


def resolve_watch_interval(cfg, *, default: float = 120.0) -> float:
    """The poll interval (seconds) for the current time window, or `default`
    when no window matches or its interval is 'off'."""
    win = cfg.window_for(datetime.now())
    if win is None or win.interval_seconds is None:
        return default
    return float(win.interval_seconds)
```

Then rewrite `main()` to build and pass the real backends (keep `--seed`, add `--no-watch`):

```python
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
            course_id=course_id, store=store, sound_files=watch_cfg.sounds)

    app = CockpitApp(cwd=cwd, course_id=course_id, draft_fn=draft_fn,
                     post_fn=post_fn, is_answered_fn=is_answered_fn,
                     fetch_events=fetch_events, chat_fn=chat_fn,
                     watch_interval=resolve_watch_interval(watch_cfg))

    seed_numbers = parse_seed_numbers(args.seed)
    if seed_numbers:
        def _seed() -> None:
            for number in seed_numbers:
                app.draft_event(build_seed_event(number, course_id))
        app.call_after_refresh(_seed)

    app.run()
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_main_wiring.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/__main__.py tests/cockpit/test_main_wiring.py
git commit -m "feat(cockpit): wire live backends + --no-watch + interval resolver"
```

---

## Task 9: Document that the cockpit is the session watcher

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Edit the doc**

In `CLAUDE.md`, under "Session start behavior", add a note:

```markdown
When running the cockpit (`python -m ed_bot.cockpit`), it BECOMES the watcher
for that session: it polls the forum, plays the watch sounds, and owns the
`watch_alerts` state. Do NOT run `/ed-watch` separately while the cockpit is up
— they share `watch_alerts` and would consume each other's events. Use
`--no-watch` to run the cockpit seed-only without polling.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: note the cockpit subsumes /ed-watch for its session"
```

---

## Final verification

- [ ] **Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (all prior tests + the new backend/loop/app/wiring tests).

- [ ] **Smoke test seed-only (no network)**

Run: `.venv/Scripts/python.exe -m ed_bot.cockpit --no-watch --seed 222`
Expected: the cockpit launches, drafts #222, no live polling.

- [ ] Then use `superpowers:finishing-a-development-branch` to open the PR.
