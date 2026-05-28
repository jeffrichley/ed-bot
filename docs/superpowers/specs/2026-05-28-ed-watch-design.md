# `ed watch` — Background Forum Watcher

**Status:** Design approved, ready for implementation plan
**Date:** 2026-05-28
**Owner:** Jeff Richey

## Goal

Poll the active EdStem course on a schedule, classify changed threads, and
alert the user — locally with a distinct sound and, when Claude Code is open,
with a chat notification — only when something actionable appears. Silent on
"nothing new" or "found but not actionable" so the user's attention (and
Claude's token budget) is preserved.

## Non-goals

- Auto-posting answers. The watcher only notifies; drafting still goes through
  `/ed-check`.
- Running without Claude Code open. Sound plays whenever `ed watch` is running,
  but chat notifications require the `Monitor` tool to be attached, which only
  happens in an active Claude session.
- Multiple courses concurrently. v1 watches one course at a time (the active
  `course_id` in `~/.ed-bot/config.yaml`).

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  ed watch  (Python process, blocking)                    │
│                                                          │
│  ┌──────────────────┐    ┌─────────────────────────┐    │
│  │ APScheduler      │───▶│ poll() — every N min    │    │
│  │  (cron rules     │    │   1. fetch threads      │    │
│  │   from yaml)     │    │   2. diff vs watch_log  │    │
│  └──────────────────┘    │   3. classify each      │    │
│                          │   4. if actionable:     │    │
│                          │      - play sound       │    │
│                          │      - emit JSON line   │    │
│                          │      - log to watch_log │    │
│                          └─────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
            │                          │
            │ stdout (one JSON/line)   │ local sound
            ▼                          ▼
   ┌──────────────────┐         ┌──────────────┐
   │ Claude Code      │         │ Speakers     │
   │ Monitor tool     │         │ (playsound3) │
   │  → chat ping     │         └──────────────┘
   └──────────────────┘
```

`ed watch` is a single blocking process. APScheduler holds the cron rules from
`watch.yaml` and fires `poll()` on configured intervals. Each poll fetches the
current thread list, diffs against the watcher's own state table, classifies
each changed thread, and for each *actionable* event plays a local sound AND
emits one JSON line to stdout. Claude Code starts the process via
`Bash(run_in_background=true)` plus the `Monitor` tool, which converts each
stdout line into a chat notification.

## Lifecycle

The user does not start the watcher manually. Instead, `ed-bot/CLAUDE.md` is
updated with a session-start instruction telling Claude to invoke
`/ed-watch start` proactively when a session opens in this project. Claude's
skill invocation does both halves in one motion: launches `ed watch` as a
background bash process and attaches the `Monitor` tool to its stdout. The
watcher dies cleanly when the Claude session ends (or earlier via
`/ed-watch stop`).

This avoids the two-stage problem of a `settings.json` SessionStart hook
(which runs shell only and cannot trigger Claude's `Monitor` tool).

Normal startup is silent — no sound and no Claude emission. The watcher only
makes itself known when an actionable event fires or a persistent error
threshold is crossed.

## Configuration — `~/.ed-bot/watch.yaml`

```yaml
course_id: 98559   # optional; falls back to config.yaml's active course_id

schedule:
  - days: [mon, tue, wed, thu, fri]
    hours: "09:00-22:00"
    interval: 5m
  - days: [mon, tue, wed, thu, fri]
    hours: "22:00-09:00"
    interval: 30m
  - days: [sat, sun]
    hours: "08:00-23:00"
    interval: 15m
  - days: [sat, sun]
    hours: "23:00-08:00"
    interval: "off"

sounds:
  new_thread:  "{ed_bot}/watch/sounds/new.wav"
  followup:    "{ed_bot}/watch/sounds/followup.wav"
  escalation:  "{ed_bot}/watch/sounds/escalation.wav"
  error:       "{ed_bot}/watch/sounds/error.wav"
```

### Schedule semantics

- Each list entry is a *window*: `(days, hours, interval)`.
- `interval: "off"` means no poll at all in that window (no API call).
- Numeric intervals accept `5m`, `30s`, `1h` (parsed via a small duration parser).
- Windows must not overlap on a given day. Validated on load; raises with a
  clear message pointing at the conflicting entries.
- Gaps (times not covered by any window) default to "off". Validator emits an
  info-level warning if any day has > 1 hour of uncovered time, in case it
  was unintentional.
- Times are local time (the machine's `tzlocal()`), not UTC. Documented in
  comments inside the bundled sample config. DST transitions are handled by
  APScheduler's cron trigger.

### Sounds

- Defaults ship inside the ed-bot wheel under `ed_bot/watch/sounds/*.wav`.
- The `{ed_bot}` token in config expands to the installed package directory.
- Files must be `.wav` (cross-platform via `playsound3`). MP3 also works but
  has more codec edge cases — `.wav` is the supported default.
- Sounds should be distinct in *timbre*, not just pitch (e.g., bell vs chime
  vs alarm vs error chord). v1 ships four bundled defaults.

## State — `watch_alerts` table

A new table in the existing tracker SQLite DB (`~/.ed-bot/state/tracker.db`),
*separate* from the existing `threads` table used by `/ed-check`. Sharing the
DB file but not the table means the watcher and manual review flow don't
interfere with each other's "have we seen this?" bookkeeping.

```sql
CREATE TABLE IF NOT EXISTS watch_alerts (
    thread_id          INTEGER PRIMARY KEY,
    last_alert_kind    TEXT NOT NULL,      -- new_thread | followup | escalation
    last_alert_at      TEXT NOT NULL,      -- ISO8601 UTC, when we alerted
    last_event_at      TEXT NOT NULL       -- the thread.updated_at we alerted on
);
```

A thread is **emitted** on a given poll if:

1. The classifier (see below) decides it is `new_thread`, `followup`, or
   `escalation`; AND
2. The pair `(thread.updated_at, kind)` differs from the row in
   `watch_alerts` for that `thread_id` (or no row exists).

Non-emitted (silent) outcomes also write to `watch_alerts` with a `kind` of
`"silent"`, so the watcher knows it has already considered this update and
should not reclassify it on the next poll unless the thread changes again.

## Classification

Implemented in `ed_bot.watch.classify`, a thin adapter over the existing
`ed_bot.classifier` module. Maps the existing classifier's output plus a
small set of escalation rules to one of four decisions:

| Decision | Condition |
|---|---|
| `new_thread` | classifier says "actionable" (project_help, setup, conceptual, logistics, teaching_moment) AND no prior emission for this `updated_at` |
| `followup` | tracker_status semantically equals `updated_since_answered` (we have a reply, the thread has new activity since) |
| `escalation` | title or first 500 chars of body matches escalation regex (medical emergency, integrity, regrade, dean, urgent — case-insensitive, word-boundary); OR the underlying classifier returns `integrity_risk` |
| `silent` | already-answered AND not a follow-up; OR category in {Social, Announcements} AND title contains no `?`; OR no relevant change since last `watch_alerts` row |

Escalation takes priority over `new_thread` and `followup`. If a thread matches
the escalation regex, it emits as `escalation` regardless of the classifier's
other output. This is intentional — escalations are the highest-signal alert
and should never be downgraded.

### Emission JSON

One line per actionable event, written to stdout (and flushed):

```json
{"kind":"new_thread","thread_id":8084123,"number":167,
 "title":"...","category":"Project 1 | Martingale",
 "url":"https://edstem.org/us/courses/98559/discussion/8084123",
 "ts":"2026-05-28T16:42:00Z"}
```

## Cross-platform sound — `ed_bot.watch.sound`

Single function `play(kind: Kind) -> None`. Uses `playsound3.playsound(path,
block=False)`. If `playsound3` is unavailable at import time on Windows, falls
back to `winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)`
so the watcher still works in stripped-down environments.

`playsound3` is added to `ed-bot` dependencies in `pyproject.toml`.

## Errors

- **Transient API/network failure**: log a warning, retry with exponential
  backoff (1m → 2m → 4m), capped at the current window's `interval`. No sound,
  no emission.
- **Persistent failure (>30 min of consecutive errors)**: play `error` sound
  once, emit one JSON line `{"kind":"error","reason":"api_unavailable_30m",
  "ts":"..."}`. Then go quiet until recovery — do not spam. On recovery, emit
  one `{"kind":"recovered", ...}` line and resume normal polling.
- **Config errors at startup**: print to stderr, exit non-zero. No sound (the
  user isn't expecting one yet).
- **Single-instance lock**: PID file at `~/.ed-bot/state/watch.pid`. On start,
  check for a live process at that PID; if alive, print the PID and exit
  non-zero. If the PID is stale (process dead), claim the lock.

## CLI surface

```
ed watch                    # start, blocking; uses ~/.ed-bot/watch.yaml
ed watch --config <path>    # override config path
ed watch --once             # run one poll and exit (for tests / manual cron)
ed watch --interval 2m      # override schedule with a single flat interval
ed watch status             # is the watcher running? Print PID, uptime, last poll
ed watch stop               # signal the running watcher to shut down cleanly
```

## Module layout

```
src/ed_bot/watch/
├── __init__.py
├── cli.py              # typer commands (registered under ed.watch)
├── config.py           # parse + validate watch.yaml
├── runner.py           # APScheduler + main loop + retry/backoff
├── poll.py             # one poll: fetch, diff, classify, emit
├── classify.py         # adapter over ed_bot.classifier + escalation rules
├── state.py            # watch_alerts table operations
├── sound.py            # cross-platform play()
├── emit.py             # JSON serialization to stdout
└── sounds/
    ├── new.wav
    ├── followup.wav
    ├── escalation.wav
    └── error.wav
```

## Testing

- **`watch.config`** — YAML parsing; schedule window validation (overlaps,
  bad days, bad hour ranges, unknown interval units, `"off"` handling); the
  `{ed_bot}` token expansion. Pure unit tests.
- **`watch.classify`** — table-driven: given (thread, prior watch_alerts row,
  classifier result), assert decision. Cover all four decision branches,
  escalation priority, and the "no change since last alert" silent case.
- **`watch.state`** — `watch_alerts` upsert/diff with a tmpfile sqlite DB.
- **`watch.poll`** — with a mocked EdStem client and a fake clock: feed
  scripted thread snapshots across multiple polls, assert correct sequence of
  emissions + state writes.
- **`watch.sound`** — mock `playsound3.playsound`; assert correct file path
  per kind. Smoke test the `winsound` fallback path on Windows.
- **`watch.runner`** — APScheduler integration with fake clock and
  `BackgroundScheduler`; assert (a) "off" windows skip polls, (b) interval
  changes at window boundaries, (c) retry/backoff state machine, (d) the
  30-min-error → emit error → silence pattern.
- **End-to-end**: `ed watch --once` against recorded EdStem fixtures, assert
  exact stdout JSON and `watch_alerts` writes.

## Changes outside the watch module

- `pyproject.toml` — add `playsound3>=1.0`, `apscheduler>=3.10`.
- `src/ed_bot/cli/main.py` — register the new `watch` typer subcommand.
- `src/ed_bot/tracker.py` — no changes required; `watch_alerts` is created
  by `watch.state` on first use (same DB file, different table).
- `ed-bot/CLAUDE.md` — append session-start instruction directing Claude to
  proactively invoke `/ed-watch start` when opening this project.
- `ed-bot/.claude/skills/ed-watch/SKILL.md` — new skill. Two subcommands:
  `start` (background-launch `ed watch`, attach `Monitor` to its stdout,
  describe the four sound kinds) and `stop` (call `ed watch stop`, detach
  Monitor).
- `~/.ed-bot/watch.yaml` — installed by `ed watch` on first run if absent,
  using sensible defaults documented above.

## Open questions deferred to implementation

These are deliberately not decided in the spec; the implementation plan can
pick concrete answers:

- Exact bundled sound files. Open-licensed source TBD during implementation
  (e.g., from freesound.org with CC0 or similar). Out of scope for the design;
  any four distinct short wavs satisfy the spec.
- Exact regex pattern for escalation keywords. The decision rule is fixed;
  the wording can be tuned during implementation with sample threads.
