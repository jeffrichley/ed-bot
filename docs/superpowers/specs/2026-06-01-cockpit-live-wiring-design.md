# Cockpit Live Wiring — Design Spec

**Date:** 2026-06-01
**Status:** Approved, ready for planning
**Scope:** Wire the cockpit's three stub hooks (`fetch_events`, `post_fn`,
`is_answered_fn`) to live EdStem backends so the cockpit watches the forum
(with sound), auto-drafts, and posts approved answers — all in one
self-contained asyncio process.

## Goal

Today the cockpit drafts real answers via the Agent SDK, but it cannot pull
live forum events (only `--seed`), and it cannot post. This work makes the full
loop live: **watch → draft → post (with resolve)**.

## Locked decisions (from brainstorming)

1. **Approve = post**, guarded by an `is_answered` staleness re-check. Hitting
   `a` posts immediately; no second confirmation. The human has already read
   the draft.
2. **The cockpit IS the watcher** for its session. It reuses the existing
   `ed_bot.watch` poll (classify + sound + the `watch_alerts` state table), so
   it plays the same sounds and inherits the dedup/escalation-handled fixes
   from PR #8. It owns `watch_alerts` while running, so **`/ed-watch` must not
   run separately** during a cockpit session (shared state would make the two
   pollers eat each other's events).
3. **Resolve behavior:** always post top-level answers as `--answer` and try to
   accept. On a `type:post` thread the accept fails ("Invalid answer
   ancestor"); that is surfaced as a one-line warning and the post still counts
   as success.
4. **Nested replies are in scope now.** Follow-up threads post via
   `comments.reply(target_comment_id, ...)`, not a new top-level answer.

## Backend API surface (verified)

From `ed_api` (`E:\workspaces\school\gt\ed-api`):

- `EdClient(region=...)` — construct; `.close()` to release.
- `client.comments.post(thread_id, content, is_answer=True) -> Comment` (`.id`).
- `client.comments.reply(comment_id, content) -> Comment`.
- `client.comments.accept(comment_id) -> None` — raises on `type:post` threads.
- `client.comments.endorse(comment_id) -> None`.
- `client.threads.get(thread_id) -> ThreadDetail` with `.type`
  (`"question" | "post" | "announcement"`), `.is_answered: bool`, `.comments`,
  `.users`.

From `ed_bot.watch`:

- `watch/poll.py:poll(course_id, fetch, store, play, sound_files)` — one poll
  cycle. Currently emits each actionable event as a JSON line to **stdout** via
  the module-level `emit`, plays a sound, and records state. All dedup +
  re-emit-guard logic lives here.
- `watch/cli.py:_build_poll_fn(course_id, store, sound_files)` — builds the
  tracker-cross-referencing `fetch(cid) -> list[dict]` closure and wires it to
  `run_poll`. The `fetch` closure is the piece worth reusing.
- `watch/sound.py:play(kind, sound_files)`, `watch/state.py:WatchAlertStore`,
  `watch/config.py` (interval windows + `sounds`).

From the cockpit:

- `cockpit/watcher.py` already has `poll_once` / `watch_loop` driving a
  `fetch_events(course_id) -> list[WatcherEvent]` against an `asyncio.Queue`.
  Nothing starts it yet.
- `cockpit/loop.py:_approve` already has the `is_answered_fn` guard → `post_fn`
  skeleton. Both backends are `None` today.

## Architecture

### 1. Refactor the watch poll for reuse (CLI behavior unchanged)

The cockpit must capture emitted events as objects, not parse stdout, and must
not duplicate the dedup logic.

- **`watch/poll.py`**: add an `on_event` parameter to `poll()`, defaulting to
  the existing stdout `emit`. Replace the hardcoded `emit(kind, ...)` call with
  `on_event(kind, thread_id=, number=, title=, category=, url=)`. The standalone
  watcher passes nothing and keeps printing JSON; the cockpit passes a collector.
- **`watch/cli.py`**: extract the `fetch` builder from `_build_poll_fn` into an
  importable module-level `build_fetch(course_id) -> FetchFn`. `_build_poll_fn`
  then calls `build_fetch` so the CLI is unchanged, and the cockpit can import
  `build_fetch` to drive `run_poll` itself.

### 2. New `cockpit/backends.py` — the three live hooks

All three wrap the **synchronous** `ed_api` / watch code in `asyncio.to_thread`
so the Textual event loop never blocks.

- **`build_fetch_events(*, course_id, store, sound_files) -> FetchEvents`**
  The builder calls `build_fetch(course_id)` **once** (one `EdClient` reused
  across polls). Returns async `fetch_events(cid)`. Each call:
  1. builds a fresh `collected: list[WatcherEvent]` and an `on_event` that
     appends `WatcherEvent(kind=..., thread_id=..., number=..., title=...,
     category=..., url=...)`;
  2. runs `run_poll(course_id=cid, fetch=fetch, store=store, play=play,
     sound_files=sound_files, on_event=on_event)` inside `asyncio.to_thread`,
     where `fetch` is the single pre-built closure;
  3. returns `collected`.
  Owns `watch_alerts` (single source of truth). Sounds play locally from the
  worker thread. `error` / `recovered` event kinds are produced by the
  standalone runner's retry layer, not by `poll()`, so the cockpit does not emit
  them; transient failures are swallowed by `poll_once` (the watcher survives).

- **`build_post_fn(*, region) -> PostFn`**
  Returns async `post_fn(*, thread_id, number, body, post_kind,
  target_comment_id) -> ActionResult`, wrapping a shared `EdClient`:
  - `post_kind == "answer"`:
    `comment = client.comments.post(thread_id, body, is_answer=True)`;
    `try: client.comments.accept(comment.id)` →
    `ActionResult(thread_id, ok=True, posted_id=comment.id, accepted=True)`.
    On accept failure:
    `ActionResult(ok=True, posted_id=comment.id, accepted=False,
    message="posted; could not accept (post-type thread) — resolve by hand")`.
    Also record the answer in the tracker (`ThreadTracker.record_answer`) so
    follow-up detection keeps working.
  - `post_kind == "reply"`:
    `comment = client.comments.reply(target_comment_id, body)` →
    `ActionResult(thread_id, ok=True, posted_id=comment.id, accepted=False)`.
    No accept attempt (nested replies are not acceptable).
  - A network exception → `ActionResult(ok=False, message=str(e))`.

- **`build_is_answered_fn(*, region) -> IsAnsweredFn`**
  Returns async `is_answered_fn(thread_id) -> bool`; runs
  `client.threads.get(thread_id).is_answered` via `to_thread`.

### 3. `cockpit/loop.py` — two correctness fixes

- The staleness guard in `_approve` applies **only when
  `payload.post_kind == "answer"`**. A follow-up reply legitimately targets an
  already-answered thread, so `is_answered=True` must not block it.
- Pass `thread_id=payload.thread_id` to both `is_answered_fn` and `post_fn`
  (they need the global thread id, not the course-local number). Widen the
  `PostFn` / `IsAnsweredFn` type aliases accordingly: `post_fn` gains a
  `thread_id` kwarg; `is_answered_fn(thread_id)` replaces `is_answered_fn(number)`.

### 4. `cockpit/app.py` — actually start the watcher

- In `on_mount`, if `self._fetch_events` is set, start the background watcher:
  create an `asyncio.Queue`, start `watch_loop(course_id, queue, fetch_events,
  interval_seconds, stop)` as a worker (producer), and a consumer worker that
  awaits `queue.get()` and calls `self.draft_event(ev)` per event (so each
  draft runs on the existing non-blocking draft worker). Set the `stop` event on
  unmount.
- The poll interval comes from `watch.yaml` (fall back to a sane default, e.g.
  120s, if unset).

### 5. `cockpit/__main__.py` — wire the real backends

- Build `WatchAlertStore` (on `~/.ed-bot/state/tracker.db`), sound files and
  interval (from `watch.yaml` via `watch.config`), and `region` (from
  `BotConfig`).
- Construct `post_fn`, `is_answered_fn`, `fetch_events` and pass all three to
  `CockpitApp` (replacing today's `None`s).
- Keep `--seed` for demo / manual injection.
- Add `--no-watch` to skip live polling (seed-only testing).

### 6. Docs

- Update the project `CLAUDE.md`: the cockpit is the watcher for its session;
  do not run `/ed-watch` separately while it is up (shared `watch_alerts`
  state).

## Edge cases (explicitly handled)

- **post-type thread**: `accept` fails → warn, post counts (decision 3).
- **is_answered guard**: skips already-answered *answers*, never *replies*.
- **EdClient lifecycle**: one client per backend builder; closed on app exit.
- **Transient poll failure**: swallowed by `poll_once`; the watch loop survives.
- **Double-watcher**: documented as unsupported; the cockpit owns `watch_alerts`.

## Testing

- **Unit (`backends.py`)** against a fake `EdClient`:
  - answer path posts as answer and accepts;
  - accept failure → `ok=True, accepted=False`, warning message;
  - reply path calls `comments.reply` and does not accept;
  - network error → `ok=False`;
  - `is_answered_fn` returns the thread's flag;
  - `fetch_events` collects emitted events into `WatcherEvent`s and offloads to
    a thread (assert it does not block; assert the collector mapping).
- **Unit (`loop.py`)**: the staleness guard blocks an already-answered *answer*
  but allows a *reply*; `thread_id` is forwarded to both backends.
- **Unit (`watch/poll.py`)**: `on_event` default still emits to stdout; a custom
  `on_event` receives the event fields and stdout stays quiet.
- **App (`app.py`)** via Textual `run_test`: with a fake `fetch_events` that
  yields one event, the watcher start path lands a queue item + draft.
- The existing `--seed` path stays green.

## Out of scope (fast-follow candidates)

- Edit-in-place of a draft before posting (the `e` hotkey is still a stub).
- `error` / `recovered` surfacing inside the cockpit (the standalone runner's
  retry/escalation layer is not reused here).
- Reply-resolution beyond posting (e.g. auto-accepting a parent answer when a
  follow-up resolves a previously-unanswered question).
