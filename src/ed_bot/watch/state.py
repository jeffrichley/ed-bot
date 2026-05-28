"""watch_alerts table — tracks which thread updates we've alerted on."""
from __future__ import annotations

import pathlib
import sqlite3
from datetime import datetime, timezone
from typing import Literal, Optional

Kind = Literal["new_thread", "followup", "escalation", "silent"]

_CREATE_TABLE = """\
CREATE TABLE IF NOT EXISTS watch_alerts (
    thread_id          INTEGER PRIMARY KEY,
    last_alert_kind    TEXT NOT NULL,
    last_alert_at      TEXT NOT NULL,
    last_event_at      TEXT NOT NULL,
    last_reply_count   INTEGER NOT NULL DEFAULT 0
);
"""

_MIGRATE_ADD_REPLY_COUNT = (
    "ALTER TABLE watch_alerts ADD COLUMN "
    "last_reply_count INTEGER NOT NULL DEFAULT 0;"
)

_UPSERT = """\
INSERT INTO watch_alerts (thread_id, last_alert_kind, last_alert_at,
                          last_event_at, last_reply_count)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT(thread_id) DO UPDATE SET
    last_alert_kind  = excluded.last_alert_kind,
    last_alert_at    = excluded.last_alert_at,
    last_event_at    = excluded.last_event_at,
    last_reply_count = excluded.last_reply_count;
"""


class WatchAlertStore:
    """Persistent record of which (thread, kind, event_at) tuples we've alerted on."""

    def __init__(self, db_path: pathlib.Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: the CLI opens the store on the main thread
        # but APScheduler dispatches polls onto a worker thread. SQLite is
        # fine with cross-thread use as long as access is serialized, which
        # APScheduler's BlockingScheduler does by default (one job at a time).
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_TABLE)
        self._migrate_add_last_reply_count()
        self._conn.commit()

    def _migrate_add_last_reply_count(self) -> None:
        cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(watch_alerts)")}
        if "last_reply_count" not in cols:
            self._conn.execute(_MIGRATE_ADD_REPLY_COUNT)

    def close(self) -> None:
        self._conn.close()

    def get(self, thread_id: int) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT last_alert_kind, last_alert_at, last_event_at, last_reply_count "
            "FROM watch_alerts WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
        return dict(row) if row else None

    def record(
        self,
        thread_id: int,
        kind: Kind,
        event_at: str,
        reply_count: int = 0,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(_UPSERT, (thread_id, kind, now, event_at, reply_count))
        self._conn.commit()

    def is_new_event(self, thread_id: int, kind: Kind, event_at: str) -> bool:
        existing = self.get(thread_id)
        if existing is None:
            return True
        return (existing["last_alert_kind"], existing["last_event_at"]) != (kind, event_at)
