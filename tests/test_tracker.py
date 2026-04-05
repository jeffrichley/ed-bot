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


class TestReplyCountIncreased:
    """Tests for reply_count_increased flag in upsert results."""

    def test_new_thread_has_no_reply_count_increased(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        with ThreadTracker(db_path) as tracker:
            result = tracker.upsert_from_list([_make_thread(reply_count=3)])
            assert result[0]["reply_count_increased"] is False

    def test_reply_count_increased_when_higher(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        with ThreadTracker(db_path) as tracker:
            tracker.upsert_from_list([_make_thread(reply_count=1)])
            result = tracker.upsert_from_list([
                _make_thread(updated_at="2026-03-31T00:00:00Z", reply_count=3)
            ])
            assert result[0]["reply_count_increased"] is True

    def test_reply_count_not_increased_when_same(self, tmp_bot_dir):
        db_path = tmp_bot_dir / "state" / "tracker.db"
        with ThreadTracker(db_path) as tracker:
            tracker.upsert_from_list([_make_thread(reply_count=2)])
            result = tracker.upsert_from_list([
                _make_thread(updated_at="2026-03-31T00:00:00Z", reply_count=2)
            ])
            assert result[0]["reply_count_increased"] is False


class TestHasUnansweredFollowup:
    """Tests for _has_unanswered_followup in review CLI."""

    def _make_user(self, user_id, role="student"):
        from unittest.mock import MagicMock
        user = MagicMock()
        user.id = user_id
        user.is_staff = role in ("staff", "admin")
        user.role = role
        return user

    def _make_comment(self, comment_id, user_id, replies=None):
        from unittest.mock import MagicMock
        c = MagicMock()
        c.id = comment_id
        c.user_id = user_id
        c.replies = replies or []
        return c

    def test_no_replies_no_followup(self):
        from ed_bot.cli.review import _has_unanswered_followup
        from unittest.mock import MagicMock

        thread = MagicMock()
        thread.comments = [self._make_comment(1, 100)]
        thread.users = {100: self._make_user(100, "staff")}
        assert _has_unanswered_followup(thread) is False

    def test_student_reply_is_unanswered(self):
        from ed_bot.cli.review import _has_unanswered_followup
        from unittest.mock import MagicMock

        student_reply = self._make_comment(2, 200)
        staff_answer = self._make_comment(1, 100, replies=[student_reply])
        thread = MagicMock()
        thread.comments = [staff_answer]
        thread.users = {
            100: self._make_user(100, "staff"),
            200: self._make_user(200, "student"),
        }
        assert _has_unanswered_followup(thread) is True

    def test_staff_reply_to_student_is_resolved(self):
        from ed_bot.cli.review import _has_unanswered_followup
        from unittest.mock import MagicMock

        staff_reply = self._make_comment(3, 100)
        student_reply = self._make_comment(2, 200, replies=[staff_reply])
        staff_answer = self._make_comment(1, 100, replies=[student_reply])
        thread = MagicMock()
        thread.comments = [staff_answer]
        thread.users = {
            100: self._make_user(100, "staff"),
            200: self._make_user(200, "student"),
        }
        assert _has_unanswered_followup(thread) is False

    def test_nested_student_followup_after_staff_reply(self):
        from ed_bot.cli.review import _has_unanswered_followup
        from unittest.mock import MagicMock

        # staff answer -> student reply -> staff reply -> student follow-up (unanswered)
        student_followup = self._make_comment(4, 200)
        staff_reply = self._make_comment(3, 100, replies=[student_followup])
        student_reply = self._make_comment(2, 200, replies=[staff_reply])
        staff_answer = self._make_comment(1, 100, replies=[student_reply])
        thread = MagicMock()
        thread.comments = [staff_answer]
        thread.users = {
            100: self._make_user(100, "staff"),
            200: self._make_user(200, "student"),
        }
        assert _has_unanswered_followup(thread) is True


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
