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

    def test_mark_checked(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        tracker = ThreadTracker(db_path)
        try:
            thread = {
                "thread_id": 100, "thread_number": 1, "title": "Test",
                "category": "General", "updated_at": "2026-04-01T10:00:00Z",
                "reply_count": 0, "is_answered": False,
            }
            tracker.upsert_from_list([thread])
            tracker.mark_checked(100)
            row = tracker._conn.execute(
                "SELECT last_checked_at FROM threads WHERE thread_id = 100"
            ).fetchone()
            assert row["last_checked_at"] is not None
        finally:
            tracker.close()

    def test_record_answer(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        tracker = ThreadTracker(db_path)
        try:
            thread = {
                "thread_id": 100, "thread_number": 1, "title": "Test",
                "category": "General", "updated_at": "2026-04-01T10:00:00Z",
                "reply_count": 0, "is_answered": False,
            }
            tracker.upsert_from_list([thread])
            tracker.record_answer(100, comment_id=99999)
            row = tracker._conn.execute(
                "SELECT our_answer_id, status FROM threads WHERE thread_id = 100"
            ).fetchone()
            assert row["our_answer_id"] == 99999
            assert row["status"] == "answered"
        finally:
            tracker.close()

    def test_get_stats(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        tracker = ThreadTracker(db_path)
        try:
            thread_100 = {
                "thread_id": 100, "thread_number": 1, "title": "Thread A",
                "category": "General", "updated_at": "2026-04-01T10:00:00Z",
                "reply_count": 0, "is_answered": False,
            }
            thread_200 = {
                "thread_id": 200, "thread_number": 2, "title": "Thread B",
                "category": "General", "updated_at": "2026-04-01T11:00:00Z",
                "reply_count": 0, "is_answered": False,
            }
            tracker.upsert_from_list([thread_100, thread_200])
            tracker.record_answer(100, comment_id=99999)
            stats = tracker.get_stats()
            assert stats["total_tracked"] == 2
            assert stats["answered_by_us"] == 1
        finally:
            tracker.close()

    def test_updated_since_answered(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        tracker = ThreadTracker(db_path)
        try:
            thread = {
                "thread_id": 100, "thread_number": 1, "title": "Test",
                "category": "General", "updated_at": "2026-04-01T10:00:00Z",
                "reply_count": 0, "is_answered": False,
            }
            tracker.upsert_from_list([thread])
            tracker.record_answer(100, comment_id=99999)
            thread["updated_at"] = "2026-04-02T10:00:00Z"
            result = tracker.upsert_from_list([thread])
            assert len(result) == 1
            assert result[0]["tracker_status"] == "updated_since_answered"
        finally:
            tracker.close()
