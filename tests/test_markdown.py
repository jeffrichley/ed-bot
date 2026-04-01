from datetime import datetime
from ed_bot.ingestion.markdown import thread_to_markdown, ThreadData, CommentData


class TestThreadToMarkdown:
    def test_basic_thread(self):
        thread = ThreadData(
            thread_id=342,
            thread_number=42,
            course_id=12345,
            semester="spring-2026",
            category="Project 1",
            subcategory="Martingale",
            type="question",
            title="get_data() returns NaN",
            content="My data has NaN values",
            author_role="student",
            is_endorsed=False,
            is_private=False,
            is_answered=False,
            has_staff_response=False,
            has_accepted_answer=False,
            created="2026-03-15T10:30:00Z",
            updated="2026-03-16T14:22:00Z",
            comments=[],
        )
        md = thread_to_markdown(thread)
        assert "thread_id: 342" in md
        assert "# get_data() returns NaN" in md
        assert "semester: spring-2026" in md
        assert "category:" in md

    def test_thread_with_comments(self):
        thread = ThreadData(
            thread_id=100,
            thread_number=1,
            course_id=54321,
            semester="spring-2026",
            category="General",
            subcategory=None,
            type="question",
            title="Test question",
            content="Question body",
            author_role="student",
            is_endorsed=True,
            is_private=False,
            is_answered=True,
            has_staff_response=True,
            has_accepted_answer=True,
            created="2026-03-15T10:30:00Z",
            updated="2026-03-16T14:22:00Z",
            comments=[
                CommentData(
                    type="answer",
                    author_role="staff",
                    content="The answer is...",
                    is_endorsed=True,
                ),
                CommentData(
                    type="comment",
                    author_role="student",
                    content="Thank you!",
                    is_endorsed=False,
                ),
            ],
        )
        md = thread_to_markdown(thread)
        assert "## Answer by staff (endorsed)" in md
        assert "The answer is..." in md
        assert "## Comment by student" in md
        assert "Thank you!" in md

    def test_frontmatter_has_required_fields(self):
        thread = ThreadData(
            thread_id=1, thread_number=1, course_id=1,
            semester="s1", category="cat", subcategory=None,
            type="question", title="t", content="c",
            author_role="student", is_endorsed=False,
            is_private=False, is_answered=False,
            has_staff_response=False, has_accepted_answer=False,
            created="2026-01-01T00:00:00Z", updated="2026-01-01T00:00:00Z",
            comments=[],
        )
        md = thread_to_markdown(thread)
        assert "---" in md
        assert "thread_id:" in md
        assert "semester:" in md
        assert "category:" in md
        assert "has_staff_response:" in md

    def test_filename_from_thread(self):
        from ed_bot.ingestion.markdown import thread_filename
        assert thread_filename(42, "get_data() returns NaN") == "0042-get-data-returns-nan.md"
        assert thread_filename(1, "Simple   Title!") == "0001-simple-title.md"
