"""ThreadTracker — SQLite-backed thread state tracking for ed-bot."""

from __future__ import annotations

import pathlib
import sqlite3
from datetime import datetime, timezone

_CREATE_TABLE = """\
CREATE TABLE IF NOT EXISTS threads (
    thread_id              INTEGER PRIMARY KEY,
    thread_number          INTEGER UNIQUE NOT NULL,
    title                  TEXT    NOT NULL DEFAULT '',
    category               TEXT    NOT NULL DEFAULT '',
    last_seen_updated_at   TEXT,
    last_checked_at        TEXT,
    reply_count_seen       INTEGER NOT NULL DEFAULT 0,
    our_answer_id          INTEGER,
    status                 TEXT    NOT NULL DEFAULT 'new',
    is_answered            INTEGER NOT NULL DEFAULT 0
);
"""

_UPSERT = """\
INSERT INTO threads (
    thread_id, thread_number, title, category,
    last_seen_updated_at, last_checked_at,
    reply_count_seen, is_answered, status
) VALUES (
    :thread_id, :thread_number, :title, :category,
    :updated_at, :now,
    :reply_count, :is_answered, :status
)
ON CONFLICT(thread_id) DO UPDATE SET
    title                = excluded.title,
    category             = excluded.category,
    last_seen_updated_at = excluded.last_seen_updated_at,
    last_checked_at      = excluded.last_checked_at,
    reply_count_seen     = excluded.reply_count_seen,
    is_answered          = excluded.is_answered,
    status               = excluded.status;
"""


class ThreadTracker:
    """Tracks EdStem thread state in a local SQLite database."""

    def __init__(self, db_path: pathlib.Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_TABLE)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mark_checked(self, thread_id: int) -> None:
        """Update last_checked_at to current UTC time for the given thread."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE threads SET last_checked_at = :now WHERE thread_id = :tid",
            {"now": now, "tid": thread_id},
        )
        self._conn.commit()

    def record_answer(self, thread_id: int, comment_id: int) -> None:
        """Record that we posted an answer to the given thread."""
        self._conn.execute(
            "UPDATE threads SET our_answer_id = :cid, status = 'answered' WHERE thread_id = :tid",
            {"cid": comment_id, "tid": thread_id},
        )
        self._conn.commit()

    def get_stats(self) -> dict:
        """Return summary counts for tracked threads."""
        total = self._conn.execute("SELECT COUNT(*) FROM threads").fetchone()[0]
        answered = self._conn.execute(
            "SELECT COUNT(*) FROM threads WHERE our_answer_id IS NOT NULL"
        ).fetchone()[0]
        return {"total_tracked": total, "answered_by_us": answered}

    def upsert_from_list(self, threads: list[dict]) -> list[dict]:
        """Upsert a batch of threads and return those that need attention.

        Each input dict must contain:
            thread_id, thread_number, title, category,
            updated_at (ISO string), reply_count, is_answered

        Returns dicts augmented with ``tracker_status``:
            - "new" — first time we see this thread
            - "updated" — timestamp changed, we haven't answered
            - "updated_since_answered" — timestamp changed after our answer
        Threads whose ``updated_at`` hasn't changed are silently skipped.
        """
        now = datetime.now(timezone.utc).isoformat()
        changed: list[dict] = []

        for t in threads:
            # Look up existing row
            row = self._conn.execute(
                "SELECT last_seen_updated_at, our_answer_id, reply_count_seen FROM threads WHERE thread_id = :tid",
                {"tid": t["thread_id"]},
            ).fetchone()

            if row is None:
                tracker_status = "new"
            elif row["last_seen_updated_at"] == t["updated_at"]:
                # Nothing changed — just refresh is_answered and move on
                self._conn.execute(
                    "UPDATE threads SET is_answered = :ans, last_checked_at = :now WHERE thread_id = :tid",
                    {"ans": int(t["is_answered"]), "now": now, "tid": t["thread_id"]},
                )
                continue
            elif row["our_answer_id"] is not None:
                tracker_status = "updated_since_answered"
            else:
                tracker_status = "updated"

            # Perform the upsert
            self._conn.execute(
                _UPSERT,
                {
                    "thread_id": t["thread_id"],
                    "thread_number": t["thread_number"],
                    "title": t["title"],
                    "category": t["category"],
                    "updated_at": t["updated_at"],
                    "now": now,
                    "reply_count": t["reply_count"],
                    "is_answered": int(t["is_answered"]),
                    "status": tracker_status,
                },
            )

            reply_count_increased = (
                row is not None and t["reply_count"] > row["reply_count_seen"]
            )
            changed.append({
                **t,
                "tracker_status": tracker_status,
                "reply_count_increased": reply_count_increased,
            })

        self._conn.commit()
        return changed
