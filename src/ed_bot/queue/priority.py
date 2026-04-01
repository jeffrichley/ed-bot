"""Priority scoring for draft queue."""

from ed_bot.engine.classifier import ThreadStatus


def compute_priority(status: ThreadStatus) -> str:
    """Compute priority level from thread status."""
    if status in (ThreadStatus.UNANSWERED, ThreadStatus.STUDENT_ONLY, ThreadStatus.PRIVATE_FLAGGED):
        return "high"
    if status == ThreadStatus.NEEDS_FOLLOWUP:
        return "medium"
    return "low"
