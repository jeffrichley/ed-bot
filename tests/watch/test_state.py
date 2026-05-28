"""Tests for WatchAlertStore — watch_alerts table."""
import pathlib
import pytest
from ed_bot.watch.state import WatchAlertStore


@pytest.fixture
def store(tmp_path: pathlib.Path):
    s = WatchAlertStore(tmp_path / "state" / "tracker.db")
    yield s
    s.close()


def test_get_returns_none_when_missing(store):
    assert store.get(123) is None


def test_record_then_get(store):
    store.record(123, "new_thread", "2026-05-28T10:00:00Z")
    row = store.get(123)
    assert row["last_alert_kind"] == "new_thread"
    assert row["last_event_at"] == "2026-05-28T10:00:00Z"
    assert row["last_alert_at"].endswith("+00:00")  # ISO UTC


def test_record_upserts(store):
    store.record(123, "new_thread", "2026-05-28T10:00:00Z")
    store.record(123, "followup", "2026-05-29T10:00:00Z")
    row = store.get(123)
    assert row["last_alert_kind"] == "followup"
    assert row["last_event_at"] == "2026-05-29T10:00:00Z"


def test_is_new_event_when_no_row(store):
    assert store.is_new_event(123, "new_thread", "2026-05-28T10:00:00Z") is True


def test_is_new_event_when_same_kind_and_event_at(store):
    store.record(123, "new_thread", "2026-05-28T10:00:00Z")
    assert store.is_new_event(123, "new_thread", "2026-05-28T10:00:00Z") is False


def test_is_new_event_when_event_at_changes(store):
    store.record(123, "new_thread", "2026-05-28T10:00:00Z")
    assert store.is_new_event(123, "new_thread", "2026-05-28T11:00:00Z") is True


def test_is_new_event_when_kind_changes(store):
    store.record(123, "new_thread", "2026-05-28T10:00:00Z")
    assert store.is_new_event(123, "followup", "2026-05-28T10:00:00Z") is True


def test_db_parent_dir_is_created(tmp_path):
    db = tmp_path / "deep" / "nested" / "tracker.db"
    s = WatchAlertStore(db)
    try:
        assert db.exists()
    finally:
        s.close()


def test_record_persists_reply_count(store):
    store.record(123, "new_thread", "2026-05-28T10:00:00Z", reply_count=7)
    row = store.get(123)
    assert row["last_reply_count"] == 7


def test_record_default_reply_count_zero(store):
    store.record(123, "new_thread", "2026-05-28T10:00:00Z")
    assert store.get(123)["last_reply_count"] == 0


def test_migration_adds_last_reply_count_to_old_db(tmp_path):
    """Existing DBs predate the column. Migration must add it."""
    import sqlite3
    db = tmp_path / "tracker.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    # Simulate the old schema explicitly (no last_reply_count column).
    conn = sqlite3.connect(str(db))
    conn.execute("""CREATE TABLE watch_alerts (
        thread_id INTEGER PRIMARY KEY,
        last_alert_kind TEXT NOT NULL,
        last_alert_at TEXT NOT NULL,
        last_event_at TEXT NOT NULL
    )""")
    conn.execute("INSERT INTO watch_alerts VALUES (1, 'new_thread', 't', 't')")
    conn.commit()
    conn.close()

    # Opening via WatchAlertStore should add the column transparently.
    s = WatchAlertStore(db)
    try:
        row = s.get(1)
        assert row["last_reply_count"] == 0  # default for backfilled rows
        # And new records work normally.
        s.record(2, "new_thread", "2026-05-28T10:00:00Z", reply_count=5)
        assert s.get(2)["last_reply_count"] == 5
    finally:
        s.close()


def test_usable_from_worker_thread(tmp_path):
    """APScheduler dispatches polls on worker threads; SQLite must allow it.

    Regression: 2026-05-28 the watcher crashed on its first scheduled poll
    with "SQLite objects created in a thread can only be used in that same
    thread" because the connection lacked check_same_thread=False.
    """
    import threading

    store = WatchAlertStore(tmp_path / "tracker.db")  # main thread
    errors: list[BaseException] = []

    def worker():
        try:
            store.record(42, "new_thread", "2026-05-28T10:00:00Z")
            assert store.is_new_event(42, "new_thread", "2026-05-28T10:00:00Z") is False
        except BaseException as e:
            errors.append(e)

    try:
        t = threading.Thread(target=worker)
        t.start()
        t.join(timeout=5)
        assert not errors, f"Worker thread raised: {errors[0]!r}"
    finally:
        store.close()
