# Thread Activity Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add SQLite-based per-thread tracking to ed-bot so `/ed-check` only surfaces threads with new or changed activity, instead of re-scanning everything.

**Architecture:** A `ThreadTracker` class wraps a SQLite database at `~/.ed-bot/state/tracker.db`. The `ed review scan` CLI command calls `EdClient.threads.list()`, diffs against the DB, and returns only new/updated threads. The `ed review approve` command records our answer's comment ID. Skills call CLI commands and never touch the DB directly.

**Tech Stack:** Python `sqlite3` stdlib, Typer CLI, ed-api `EdClient`, pytest

---

## File Structure

| File | Responsibility |
|------|---------------|
| Create: `src/ed_bot/tracker.py` | `ThreadTracker` class — SQLite CRUD, diffing logic |
| Create: `tests/test_tracker.py` | Unit tests for `ThreadTracker` |
| Modify: `src/ed_bot/cli/review.py` | Add `scan` command, update `approve` to record answer ID |
| Modify: `tests/test_cli.py` | CLI smoke tests for new `scan` command |
| Modify: `.claude/skills/ed-check/SKILL.md` | Use `ed review scan` instead of `ed-api threads list` |
| Modify: `.claude/skills/ed-status/SKILL.md` | Add tracker stats to dashboard |

---

### Task 1: ThreadTracker — Schema and Upsert

**Files:**
- Create: `tests/test_tracker.py`
- Create: `src/ed_bot/tracker.py`

- [ ] **Step 1: Write failing test for DB creation**

```python
"""Tests for ThreadTracker."""

import datetime

import pytest

from ed_bot.tracker import ThreadTracker


class TestThreadTracker:
    """Tests for the ThreadTracker SQLite store."""

    def test_creates_db_on_init(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        assert not db_path.exists()
        ThreadTracker(db_path)
        assert db_path.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:\workspaces\school\gt\ed-bot && python -m pytest tests/test_tracker.py::TestThreadTracker::test_creates_db_on_init -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ed_bot.tracker'`

- [ ] **Step 3: Write minimal ThreadTracker with schema creation**

Create `src/ed_bot/tracker.py`:

```python
"""Per-thread activity tracker backed by SQLite."""

import pathlib
import sqlite3
from datetime import datetime, timezone


class ThreadTracker:
    """Tracks per-thread state to detect new activity."""

    def __init__(self, db_path: pathlib.Path):
        self.db_path = pathlib.Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS threads (
                thread_id       INTEGER PRIMARY KEY,
                thread_number   INTEGER UNIQUE NOT NULL,
                title           TEXT NOT NULL DEFAULT '',
                category        TEXT NOT NULL DEFAULT '',
                last_seen_updated_at TEXT,
                last_checked_at TEXT,
                reply_count_seen INTEGER NOT NULL DEFAULT 0,
                our_answer_id   INTEGER,
                status          TEXT NOT NULL DEFAULT 'new',
                is_answered     INTEGER NOT NULL DEFAULT 0
            )
        """)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:\workspaces\school\gt\ed-bot && python -m pytest tests/test_tracker.py::TestThreadTracker::test_creates_db_on_init -v`
Expected: PASS

- [ ] **Step 5: Write failing test for upsert_from_list**

Append to `tests/test_tracker.py` inside the `TestThreadTracker` class:

```python
    def test_upsert_new_thread(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        tracker = ThreadTracker(db_path)

        threads = [
            {
                "thread_id": 100,
                "thread_number": 1,
                "title": "Test thread",
                "category": "General",
                "updated_at": "2026-04-01T10:00:00Z",
                "reply_count": 2,
                "is_answered": True,
            }
        ]
        changed = tracker.upsert_from_list(threads)

        assert len(changed) == 1
        assert changed[0]["tracker_status"] == "new"
        assert changed[0]["thread_number"] == 1

    def test_upsert_unchanged_thread(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        tracker = ThreadTracker(db_path)

        threads = [
            {
                "thread_id": 100,
                "thread_number": 1,
                "title": "Test thread",
                "category": "General",
                "updated_at": "2026-04-01T10:00:00Z",
                "reply_count": 2,
                "is_answered": True,
            }
        ]
        tracker.upsert_from_list(threads)
        changed = tracker.upsert_from_list(threads)

        assert len(changed) == 0

    def test_upsert_updated_thread(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        tracker = ThreadTracker(db_path)

        threads_v1 = [
            {
                "thread_id": 100,
                "thread_number": 1,
                "title": "Test thread",
                "category": "General",
                "updated_at": "2026-04-01T10:00:00Z",
                "reply_count": 2,
                "is_answered": True,
            }
        ]
        tracker.upsert_from_list(threads_v1)

        threads_v2 = [
            {
                "thread_id": 100,
                "thread_number": 1,
                "title": "Test thread",
                "category": "General",
                "updated_at": "2026-04-02T10:00:00Z",
                "reply_count": 3,
                "is_answered": True,
            }
        ]
        changed = tracker.upsert_from_list(threads_v2)

        assert len(changed) == 1
        assert changed[0]["tracker_status"] == "updated"
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd E:\workspaces\school\gt\ed-bot && python -m pytest tests/test_tracker.py -v`
Expected: FAIL — `AttributeError: 'ThreadTracker' object has no attribute 'upsert_from_list'`

- [ ] **Step 7: Implement upsert_from_list**

Add to `src/ed_bot/tracker.py` in the `ThreadTracker` class:

```python
    def upsert_from_list(self, threads: list[dict]) -> list[dict]:
        """Upsert threads from API list response. Returns only new/changed threads.

        Each dict must have: thread_id, thread_number, title, category,
        updated_at (ISO string), reply_count, is_answered.

        Returns dicts with an added 'tracker_status' field:
        - "new": thread not previously seen
        - "updated": updated_at changed since last seen
        - "updated_since_answered": updated_at changed AND we posted an answer
        """
        changed = []
        for t in threads:
            row = self._conn.execute(
                "SELECT last_seen_updated_at, our_answer_id FROM threads WHERE thread_id = ?",
                (t["thread_id"],),
            ).fetchone()

            updated_at = t["updated_at"] or ""

            if row is None:
                status = "new"
            elif row["last_seen_updated_at"] == updated_at:
                self._conn.execute(
                    "UPDATE threads SET is_answered = ? WHERE thread_id = ?",
                    (int(t["is_answered"]), t["thread_id"]),
                )
                self._conn.commit()
                continue
            elif row["our_answer_id"] is not None:
                status = "updated_since_answered"
            else:
                status = "updated"

            self._conn.execute(
                """INSERT INTO threads
                       (thread_id, thread_number, title, category,
                        last_seen_updated_at, reply_count_seen, is_answered, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(thread_id) DO UPDATE SET
                       title = excluded.title,
                       category = excluded.category,
                       last_seen_updated_at = excluded.last_seen_updated_at,
                       reply_count_seen = excluded.reply_count_seen,
                       is_answered = excluded.is_answered,
                       status = excluded.status
                """,
                (
                    t["thread_id"],
                    t["thread_number"],
                    t["title"],
                    t["category"],
                    updated_at,
                    t["reply_count"],
                    int(t["is_answered"]),
                    status,
                ),
            )
            self._conn.commit()

            result = dict(t)
            result["tracker_status"] = status
            changed.append(result)

        return changed
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd E:\workspaces\school\gt\ed-bot && python -m pytest tests/test_tracker.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 9: Commit**

```bash
cd E:\workspaces\school\gt\ed-bot
git add src/ed_bot/tracker.py tests/test_tracker.py
git commit -m "feat: ThreadTracker with schema creation and upsert_from_list"
```

---

### Task 2: ThreadTracker — mark_checked and record_answer

**Files:**
- Modify: `tests/test_tracker.py`
- Modify: `src/ed_bot/tracker.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_tracker.py` inside the `TestThreadTracker` class:

```python
    def test_mark_checked(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        tracker = ThreadTracker(db_path)

        tracker.upsert_from_list([
            {
                "thread_id": 100,
                "thread_number": 1,
                "title": "Test",
                "category": "General",
                "updated_at": "2026-04-01T10:00:00Z",
                "reply_count": 0,
                "is_answered": False,
            }
        ])
        tracker.mark_checked(100)

        row = tracker._conn.execute(
            "SELECT last_checked_at FROM threads WHERE thread_id = 100"
        ).fetchone()
        assert row["last_checked_at"] is not None

    def test_record_answer(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        tracker = ThreadTracker(db_path)

        tracker.upsert_from_list([
            {
                "thread_id": 100,
                "thread_number": 1,
                "title": "Test",
                "category": "General",
                "updated_at": "2026-04-01T10:00:00Z",
                "reply_count": 0,
                "is_answered": False,
            }
        ])
        tracker.record_answer(100, comment_id=99999)

        row = tracker._conn.execute(
            "SELECT our_answer_id, status FROM threads WHERE thread_id = 100"
        ).fetchone()
        assert row["our_answer_id"] == 99999
        assert row["status"] == "answered"

    def test_updated_since_answered(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        tracker = ThreadTracker(db_path)

        tracker.upsert_from_list([
            {
                "thread_id": 100,
                "thread_number": 1,
                "title": "Test",
                "category": "General",
                "updated_at": "2026-04-01T10:00:00Z",
                "reply_count": 1,
                "is_answered": True,
            }
        ])
        tracker.record_answer(100, comment_id=99999)

        changed = tracker.upsert_from_list([
            {
                "thread_id": 100,
                "thread_number": 1,
                "title": "Test",
                "category": "General",
                "updated_at": "2026-04-02T10:00:00Z",
                "reply_count": 2,
                "is_answered": True,
            }
        ])

        assert len(changed) == 1
        assert changed[0]["tracker_status"] == "updated_since_answered"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd E:\workspaces\school\gt\ed-bot && python -m pytest tests/test_tracker.py -v`
Expected: FAIL — `AttributeError: 'ThreadTracker' object has no attribute 'mark_checked'`

- [ ] **Step 3: Implement mark_checked and record_answer**

Add to `src/ed_bot/tracker.py` in the `ThreadTracker` class:

```python
    def mark_checked(self, thread_id: int) -> None:
        """Record that we fetched the full thread detail."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE threads SET last_checked_at = ? WHERE thread_id = ?",
            (now, thread_id),
        )
        self._conn.commit()

    def record_answer(self, thread_id: int, comment_id: int) -> None:
        """Record that we posted an answer on this thread."""
        self._conn.execute(
            "UPDATE threads SET our_answer_id = ?, status = 'answered' WHERE thread_id = ?",
            (comment_id, thread_id),
        )
        self._conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:\workspaces\school\gt\ed-bot && python -m pytest tests/test_tracker.py -v`
Expected: PASS (all 7 tests)

- [ ] **Step 5: Commit**

```bash
cd E:\workspaces\school\gt\ed-bot
git add src/ed_bot/tracker.py tests/test_tracker.py
git commit -m "feat: ThreadTracker mark_checked and record_answer methods"
```

---

### Task 3: ThreadTracker — get_stats

**Files:**
- Modify: `tests/test_tracker.py`
- Modify: `src/ed_bot/tracker.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_tracker.py` inside the `TestThreadTracker` class:

```python
    def test_get_stats(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        tracker = ThreadTracker(db_path)

        tracker.upsert_from_list([
            {
                "thread_id": 100,
                "thread_number": 1,
                "title": "Thread A",
                "category": "General",
                "updated_at": "2026-04-01T10:00:00Z",
                "reply_count": 1,
                "is_answered": True,
            },
            {
                "thread_id": 200,
                "thread_number": 2,
                "title": "Thread B",
                "category": "General",
                "updated_at": "2026-04-01T11:00:00Z",
                "reply_count": 0,
                "is_answered": False,
            },
        ])
        tracker.record_answer(100, comment_id=99999)

        stats = tracker.get_stats()
        assert stats["total_tracked"] == 2
        assert stats["answered_by_us"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:\workspaces\school\gt\ed-bot && python -m pytest tests/test_tracker.py::TestThreadTracker::test_get_stats -v`
Expected: FAIL — `AttributeError: 'ThreadTracker' object has no attribute 'get_stats'`

- [ ] **Step 3: Implement get_stats**

Add to `src/ed_bot/tracker.py` in the `ThreadTracker` class:

```python
    def get_stats(self) -> dict:
        """Return summary statistics from the tracker DB."""
        total = self._conn.execute("SELECT COUNT(*) FROM threads").fetchone()[0]
        answered_by_us = self._conn.execute(
            "SELECT COUNT(*) FROM threads WHERE our_answer_id IS NOT NULL"
        ).fetchone()[0]
        return {
            "total_tracked": total,
            "answered_by_us": answered_by_us,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:\workspaces\school\gt\ed-bot && python -m pytest tests/test_tracker.py -v`
Expected: PASS (all 8 tests)

- [ ] **Step 5: Commit**

```bash
cd E:\workspaces\school\gt\ed-bot
git add src/ed_bot/tracker.py tests/test_tracker.py
git commit -m "feat: ThreadTracker get_stats for dashboard"
```

---

### Task 4: CLI — `ed review scan` command

**Files:**
- Modify: `src/ed_bot/cli/review.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI smoke test**

Add to `tests/test_cli.py` (find the existing test class for CLI help tests and add):

```python
    def test_review_scan_help(self):
        from typer.testing import CliRunner
        from ed_bot.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["review", "scan", "--help"])
        assert result.exit_code == 0
        assert "Scan for new or updated threads" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:\workspaces\school\gt\ed-bot && python -m pytest tests/test_cli.py::TestCLIHelp::test_review_scan_help -v`
Expected: FAIL — no such command "scan"

- [ ] **Step 3: Implement the scan command**

Add to `src/ed_bot/cli/review.py` after the existing imports at the top of the file:

```python
@app.command()
def scan(
    limit: int = typer.Option(50, "--limit", help="Number of threads to fetch"),
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Scan for new or updated threads since last check."""
    from ed_api import EdClient
    from ed_bot.config import BotConfig
    from ed_bot.tracker import ThreadTracker

    config = BotConfig.load(_get_bot_dir(bot_dir))
    client = EdClient(region=config.region)
    tracker = ThreadTracker(config.state_dir / "tracker.db")

    api_threads = client.threads.list(config.course_id, limit=limit)

    thread_dicts = [
        {
            "thread_id": t.id,
            "thread_number": t.number,
            "title": t.title,
            "category": t.category,
            "updated_at": t.updated_at.isoformat() if t.updated_at else "",
            "reply_count": t.reply_count,
            "is_answered": t.is_answered,
        }
        for t in api_threads
        if not t.is_pinned
    ]

    changed = tracker.upsert_from_list(thread_dicts)
    tracker.close()

    if json_output:
        import json
        typer.echo(json.dumps(changed))
    else:
        if not changed:
            console.print("No new or updated threads.")
        else:
            for t in changed:
                status_icon = {"new": "🆕", "updated": "🔄", "updated_since_answered": "⚠️"}.get(
                    t["tracker_status"], "?"
                )
                console.print(
                    f"  {status_icon} #{t['thread_number']} {t['title']} [{t['tracker_status']}]"
                )
            console.print(f"\n{len(changed)} thread(s) need attention.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:\workspaces\school\gt\ed-bot && python -m pytest tests/test_cli.py::TestCLIHelp::test_review_scan_help -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd E:\workspaces\school\gt\ed-bot
git add src/ed_bot/cli/review.py tests/test_cli.py
git commit -m "feat: ed review scan command — surfaces only changed threads"
```

---

### Task 5: CLI — Update `approve` to record answer ID

**Files:**
- Modify: `src/ed_bot/cli/review.py`

- [ ] **Step 1: Update the approve command**

In `src/ed_bot/cli/review.py`, modify the `approve` function. After the line `client.comments.post(...)` (line 123), capture the return value and record it in the tracker. The modified section should be:

Replace the existing approve function body (lines 104–131) with:

```python
    """Approve and post a draft."""
    from ed_api import EdClient
    from ed_bot.config import BotConfig
    from ed_bot.queue.manager import DraftQueue
    from ed_bot.tracker import ThreadTracker

    config = BotConfig.load(_get_bot_dir(bot_dir))
    queue = DraftQueue(config.drafts_dir)
    draft = queue.get(draft_id)

    if not draft:
        err_console.print(f"[red]Draft {draft_id} not found.[/red]")
        raise typer.Exit(1)

    client = EdClient(region=config.region)

    if endorse:
        client.threads.endorse(draft.thread_id)
        action = "endorsed"
    else:
        comment = client.comments.post(draft.thread_id, draft.content, is_answer=as_answer)
        action = "posted as answer" if as_answer else "posted"

        tracker = ThreadTracker(config.state_dir / "tracker.db")
        tracker.record_answer(draft.thread_id, comment.id)
        tracker.close()

    queue.remove(draft_id)

    if json_output:
        typer.echo(json.dumps({"status": action, "draft_id": draft_id, "thread_id": draft.thread_id}))
    else:
        console.print(f"[green]Draft {draft_id} {action} on thread {draft.thread_id}.[/green]")
```

- [ ] **Step 2: Run existing tests to verify nothing broke**

Run: `cd E:\workspaces\school\gt\ed-bot && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
cd E:\workspaces\school\gt\ed-bot
git add src/ed_bot/cli/review.py
git commit -m "feat: record our_answer_id in tracker when approving drafts"
```

---

### Task 6: Update `/ed-check` skill

**Files:**
- Modify: `.claude/skills/ed-check/SKILL.md`

- [ ] **Step 1: Update the skill**

Replace the Phase 1 section of `.claude/skills/ed-check/SKILL.md`. The new Phase 1 should be:

Replace from `## Phase 1: Scan the Forum` through the end of Phase 1 (up to but not including `## Phase 2: Present Report`) with:

```markdown
## Phase 1: Scan the Forum

Fetch threads with new activity since last check.

```bash
cd E:\workspaces\school\gt\ed
ed review scan --limit 50 --json
```

This returns ONLY threads that have changed since last check:
- `tracker_status: "new"` — never seen before
- `tracker_status: "updated"` — `updated_at` moved since last seen
- `tracker_status: "updated_since_answered"` — we posted an answer but the thread has new activity (follow-up question)

If the result is empty (`[]`), the forum is caught up — report that and offer next actions.

For each returned thread, fetch the full detail:
```bash
ed-api --quiet threads get 91346:<thread_number> --json
```

Read the question and any existing comments. Classify each:
- **Question type:** logistics, setup, conceptual, project_help, teaching_moment, integrity_risk
- **Confidence level:**
  - Search the knowledge base: `qmd --quiet search "<thread title and key phrases>" --data-dir ~/.ed-bot/pyqmd --json --top-k 5`
  - HIGH: found similar past threads with staff answers
  - MEDIUM: found related content but no direct match
  - LOW: no relevant results
  - SKIP: administrative, integrity, or non-content question
```

Also update the Phase 2 report template to include the new tracker statuses. Add after the existing report format:

```markdown
For threads with `updated_since_answered` status, use this icon:

🔁 #1765 "Manual Strategy - Performance Table" — FOLLOW-UP
   We answered this thread but it has new activity. Fetch and check.
```

- [ ] **Step 2: Verify the skill file is valid markdown**

Read the file and confirm the structure is correct.

- [ ] **Step 3: Commit**

```bash
cd E:\workspaces\school\gt\ed-bot
git add .claude/skills/ed-check/SKILL.md
git commit -m "feat: update /ed-check skill to use ed review scan"
```

---

### Task 7: Update `/ed-status` skill

**Files:**
- Modify: `.claude/skills/ed-status/SKILL.md`

- [ ] **Step 1: Update the skill**

Add a new step between the existing Step 2 and Step 3. Insert after `## Step 2: Knowledge base stats`:

```markdown
## Step 2b: Tracker stats

```bash
cd E:\workspaces\school\gt\ed
ed review scan --limit 100 --json
```

Count threads by `tracker_status`: new, updated, updated_since_answered.
```

Update the dashboard template in Step 3 to include tracker info:

```markdown
```
EdStem Dashboard — CS 7646 Spring 2026
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Activity Since Last Check:
  New threads:      X
  Updated:          X
  Follow-ups:       X (threads we answered with new activity)

Knowledge Base:
  Threads:   38,837 chunks (5 semesters)
  Projects:  348 chunks
  Lectures:  3,859 chunks
  Pages:     447 chunks

Run /ed-check to scan and draft answers.
```
```

- [ ] **Step 2: Verify the skill file is valid markdown**

Read the file and confirm the structure is correct.

- [ ] **Step 3: Commit**

```bash
cd E:\workspaces\school\gt\ed-bot
git add .claude/skills/ed-status/SKILL.md
git commit -m "feat: update /ed-status skill to show tracker activity stats"
```

---

### Task 8: Integration test — full scan cycle

**Files:**
- Modify: `tests/test_tracker.py`

- [ ] **Step 1: Write integration test for full lifecycle**

Append to `tests/test_tracker.py`:

```python
class TestTrackerLifecycle:
    """Integration test for the full scan → check → answer → rescan cycle."""

    def test_full_lifecycle(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        tracker = ThreadTracker(db_path)

        # First scan: thread is new
        threads_v1 = [
            {
                "thread_id": 100,
                "thread_number": 1,
                "title": "How does MACD work?",
                "category": "Project 8 | Strategy Evaluation >",
                "updated_at": "2026-04-01T10:00:00Z",
                "reply_count": 0,
                "is_answered": False,
            }
        ]
        changed = tracker.upsert_from_list(threads_v1)
        assert len(changed) == 1
        assert changed[0]["tracker_status"] == "new"

        # Mark as checked (we fetched full detail)
        tracker.mark_checked(100)

        # We post an answer
        tracker.record_answer(100, comment_id=55555)

        # Second scan: same updated_at, nothing changed
        changed = tracker.upsert_from_list(threads_v1)
        assert len(changed) == 0

        # Third scan: student replied (updated_at moved)
        threads_v2 = [
            {
                "thread_id": 100,
                "thread_number": 1,
                "title": "How does MACD work?",
                "category": "Project 8 | Strategy Evaluation >",
                "updated_at": "2026-04-02T15:30:00Z",
                "reply_count": 2,
                "is_answered": True,
            }
        ]
        changed = tracker.upsert_from_list(threads_v2)
        assert len(changed) == 1
        assert changed[0]["tracker_status"] == "updated_since_answered"

        # Stats reflect our answer
        stats = tracker.get_stats()
        assert stats["answered_by_us"] == 1
        assert stats["total_tracked"] == 1
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd E:\workspaces\school\gt\ed-bot && python -m pytest tests/test_tracker.py::TestTrackerLifecycle -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `cd E:\workspaces\school\gt\ed-bot && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
cd E:\workspaces\school\gt\ed-bot
git add tests/test_tracker.py
git commit -m "test: integration test for full tracker lifecycle"
```
