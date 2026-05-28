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
