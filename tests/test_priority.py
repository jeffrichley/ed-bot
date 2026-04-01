from ed_bot.queue.priority import compute_priority
from ed_bot.engine.classifier import ThreadStatus


class TestPriority:
    def test_unanswered_is_high(self):
        assert compute_priority(ThreadStatus.UNANSWERED) == "high"

    def test_student_only_is_high(self):
        assert compute_priority(ThreadStatus.STUDENT_ONLY) == "high"

    def test_needs_followup_is_medium(self):
        assert compute_priority(ThreadStatus.NEEDS_FOLLOWUP) == "medium"

    def test_staff_answered_is_low(self):
        assert compute_priority(ThreadStatus.STAFF_ANSWERED) == "low"
