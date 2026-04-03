"""Tests for ThreadTracker — schema creation and upsert logic."""

import sqlite3

from ed_bot.tracker import ThreadTracker


def _make_thread(
    thread_id=1,
    thread_number=100,
    title="Help with project 1",
    category="General",
    updated_at="2026-03-30T12:00:00Z",
    reply_count=0,
    is_answered=False,
):
    return dict(
        thread_id=thread_id,
        thread_number=thread_number,
        title=title,
        category=category,
        updated_at=updated_at,
        reply_count=reply_count,
        is_answered=is_answered,
    )


class TestThreadTracker:
    def test_creates_db_on_init(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        tracker = ThreadTracker(db_path)
        try:
            assert db_path.exists()
            # Verify the threads table exists
            conn = sqlite3.connect(db_path)
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='threads'"
            )
            assert cur.fetchone() is not None
            conn.close()
        finally:
            tracker.close()

    def test_upsert_new_thread(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        tracker = ThreadTracker(db_path)
        try:
            thread = _make_thread()
            result = tracker.upsert_from_list([thread])
            assert len(result) == 1
            assert result[0]["tracker_status"] == "new"
            assert result[0]["thread_id"] == 1
            assert result[0]["thread_number"] == 100
        finally:
            tracker.close()

    def test_upsert_unchanged_thread(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        tracker = ThreadTracker(db_path)
        try:
            thread = _make_thread()
            tracker.upsert_from_list([thread])
            # Second call with same updated_at should return empty
            result = tracker.upsert_from_list([thread])
            assert result == []
        finally:
            tracker.close()

    def test_upsert_updated_thread(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        tracker = ThreadTracker(db_path)
        try:
            thread = _make_thread()
            tracker.upsert_from_list([thread])
            # Update the timestamp
            thread["updated_at"] = "2026-03-31T08:00:00Z"
            result = tracker.upsert_from_list([thread])
            assert len(result) == 1
            assert result[0]["tracker_status"] == "updated"
        finally:
            tracker.close()

    def test_upsert_updated_since_answered(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        tracker = ThreadTracker(db_path)
        try:
            thread = _make_thread()
            tracker.upsert_from_list([thread])
            # Simulate that we posted an answer
            tracker._conn.execute(
                "UPDATE threads SET our_answer_id = 999 WHERE thread_id = 1"
            )
            tracker._conn.commit()
            # Now upsert with a newer timestamp
            thread["updated_at"] = "2026-03-31T08:00:00Z"
            result = tracker.upsert_from_list([thread])
            assert len(result) == 1
            assert result[0]["tracker_status"] == "updated_since_answered"
        finally:
            tracker.close()
