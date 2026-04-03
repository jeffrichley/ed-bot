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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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
                "SELECT last_seen_updated_at, our_answer_id FROM threads WHERE thread_id = :tid",
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
                self._conn.commit()
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
            self._conn.commit()

            changed.append({**t, "tracker_status": tracker_status})

        return changed
