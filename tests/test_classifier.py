from ed_bot.engine.classifier import ThreadClassifier, ThreadStatus, QuestionType


class TestThreadStatus:
    def test_unanswered(self):
        status = ThreadClassifier.classify_status(
            comment_count=0, has_staff_response=False, is_endorsed=False, is_answered=False
        )
        assert status == ThreadStatus.UNANSWERED

    def test_student_only(self):
        status = ThreadClassifier.classify_status(
            comment_count=3, has_staff_response=False, is_endorsed=False, is_answered=False
        )
        assert status == ThreadStatus.STUDENT_ONLY

    def test_staff_answered(self):
        status = ThreadClassifier.classify_status(
            comment_count=2, has_staff_response=True, is_endorsed=False, is_answered=True
        )
        assert status == ThreadStatus.STAFF_ANSWERED

    def test_endorsed(self):
        status = ThreadClassifier.classify_status(
            comment_count=1, has_staff_response=False, is_endorsed=True, is_answered=True
        )
        assert status == ThreadStatus.ENDORSED


class TestQuestionType:
    def test_all_types_exist(self):
        assert QuestionType.LOGISTICS
        assert QuestionType.SETUP
        assert QuestionType.CONCEPTUAL
        assert QuestionType.PROJECT_HELP
        assert QuestionType.TEACHING_MOMENT
        assert QuestionType.INTEGRITY_RISK


class TestNeedsAttention:
    def test_unanswered_needs_attention(self):
        assert ThreadClassifier.needs_attention(ThreadStatus.UNANSWERED) is True

    def test_student_only_needs_attention(self):
        assert ThreadClassifier.needs_attention(ThreadStatus.STUDENT_ONLY) is True

    def test_staff_answered_does_not(self):
        assert ThreadClassifier.needs_attention(ThreadStatus.STAFF_ANSWERED) is False

    def test_endorsed_does_not(self):
        assert ThreadClassifier.needs_attention(ThreadStatus.ENDORSED) is False
