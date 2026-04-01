"""Thread status and question type classification."""

from enum import Enum


class ThreadStatus(str, Enum):
    UNANSWERED = "unanswered"
    STUDENT_ONLY = "student_only"
    NEEDS_FOLLOWUP = "needs_followup"
    ENDORSED = "endorsed"
    STAFF_ANSWERED = "staff_answered"
    RESOLVED = "resolved"
    PRIVATE_FLAGGED = "private_flagged"


class QuestionType(str, Enum):
    LOGISTICS = "logistics"
    SETUP = "setup"
    CONCEPTUAL = "conceptual"
    PROJECT_HELP = "project_help"
    TEACHING_MOMENT = "teaching_moment"
    INTEGRITY_RISK = "integrity_risk"


ATTENTION_STATUSES = {
    ThreadStatus.UNANSWERED,
    ThreadStatus.STUDENT_ONLY,
    ThreadStatus.NEEDS_FOLLOWUP,
    ThreadStatus.PRIVATE_FLAGGED,
}


class ThreadClassifier:
    """Classifies threads by status and question type."""

    @staticmethod
    def classify_status(
        comment_count: int,
        has_staff_response: bool,
        is_endorsed: bool,
        is_answered: bool,
        needs_followup: bool = False,
    ) -> ThreadStatus:
        """Classify thread status from metadata."""
        if is_endorsed:
            return ThreadStatus.ENDORSED
        if comment_count == 0:
            return ThreadStatus.UNANSWERED
        if has_staff_response:
            if needs_followup:
                return ThreadStatus.NEEDS_FOLLOWUP
            return ThreadStatus.STAFF_ANSWERED
        return ThreadStatus.STUDENT_ONLY

    @staticmethod
    def needs_attention(status: ThreadStatus) -> bool:
        """Check if a thread status requires attention."""
        return status in ATTENTION_STATUSES

    @staticmethod
    def priority_score(status: ThreadStatus) -> int:
        """Return priority score (higher = more urgent)."""
        scores = {
            ThreadStatus.PRIVATE_FLAGGED: 100,
            ThreadStatus.UNANSWERED: 90,
            ThreadStatus.STUDENT_ONLY: 70,
            ThreadStatus.NEEDS_FOLLOWUP: 50,
            ThreadStatus.ENDORSED: 0,
            ThreadStatus.STAFF_ANSWERED: 0,
            ThreadStatus.RESOLVED: 0,
        }
        return scores.get(status, 0)
