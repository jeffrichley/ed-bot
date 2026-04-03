# Thread Activity Tracker — Design Spec

**Date:** 2026-04-03
**Status:** Approved

## Problem

`/ed-check` currently skips any thread with `is_answered: true`. But students post follow-up questions on answered threads, other students reply without staff oversight, and threads we answered can get new activity. We have no way to detect this without re-scanning every thread every time.

## Solution

A SQLite-based per-thread tracker inside `ed-bot` that records the last-observed `updated_at` for each thread. When the CLI fetches threads from the API, it diffs against the DB and surfaces only threads with new activity. Silence means nothing changed.

## Architecture

### Storage

SQLite database at `~/.ed-bot/state/tracker.db`.

Single `threads` table:

| Column                 | Type         | Notes                                     |
|------------------------|--------------|-------------------------------------------|
| `thread_id`            | INTEGER PK   | EdStem global ID                          |
| `thread_number`        | INTEGER UNIQUE | Course-local number                     |
| `title`                | TEXT         |                                           |
| `category`             | TEXT         |                                           |
| `last_seen_updated_at` | TEXT (ISO)   | `updated_at` from last API fetch          |
| `last_checked_at`      | TEXT (ISO)   | When we last fetched full thread detail   |
| `reply_count_seen`     | INTEGER      | Reply count when last observed            |
| `our_answer_id`        | INTEGER NULL | Comment ID if we posted an answer         |
| `status`               | TEXT         | `new`, `answered`, `watching`, `skipped`, `human_required` |
| `is_answered`          | INTEGER      | EdStem's `is_answered` flag, snapshotted  |

### Tracking logic (all inside `ed-bot`)

Three integration points, all in existing code paths:

1. **Thread list fetch** — wherever `ed-bot` calls `EdClient.threads.list()`, it upserts each thread into the DB. Compares incoming `updated_at` against stored `last_seen_updated_at` to classify:
   - `new` — thread not in DB
   - `updated` — `updated_at` moved since `last_seen_updated_at`
   - `unchanged` — same timestamp, skip

2. **Thread detail fetch** — when `ed-bot` calls `EdClient.threads.get()`, it updates `last_checked_at` in the DB.

3. **Answer posting** — when `ed-bot` posts a comment via `EdClient` with the answer flag, it stores the returned comment ID in `our_answer_id` and sets status to `answered`.

### New CLI command

```bash
ed review scan --json
```

Returns only threads that need attention:
- **New**: not in the DB yet (`tracker_status: "new"`)
- **Updated since we answered**: `our_answer_id` is set AND `updated_at` moved (`tracker_status: "updated_since_answered"`)
- **Updated**: `updated_at` moved since `last_seen_updated_at` (`tracker_status: "updated"`)
- Returns empty list `[]` if everything is unchanged

Each returned thread object includes a `tracker_status` field alongside the normal thread fields.

### Skill integration

The `/ed-check` skill calls `ed review scan --json` instead of `ed-api threads list`. It receives only changed threads, classifies them as before (question type, confidence level), and presents the report. The DB is invisible to the skill.

The `/ed-answer` skill workflow is unchanged — it calls `ed-api comments post --answer` which now has the side effect of recording `our_answer_id` in the tracker.

## Boundaries

- **`ed-api`** — unchanged, stays stateless. Pure API client.
- **`py-qmd`** — unchanged.
- **Knowledge base ingestion** — separate concern, continues using `last-sync.json` for per-semester sync timestamps.
- **Draft queue** — separate concern, continues using JSON files in `~/.ed-bot/drafts/`.

## Implementation notes

- Use Python `sqlite3` stdlib module (no new dependencies).
- DB file auto-created on first use with `CREATE TABLE IF NOT EXISTS`.
- The tracker module should be a standalone class (e.g., `ed_bot.tracker.ThreadTracker`) with methods: `upsert_from_list()`, `mark_checked()`, `record_answer()`, `get_changed()`.
- The `ed review scan` command instantiates the tracker, calls `EdClient.threads.list()`, runs `upsert_from_list()`, then calls `get_changed()` and outputs the result.
