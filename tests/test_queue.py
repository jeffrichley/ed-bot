import pathlib
import json
from ed_bot.queue.manager import DraftQueue, Draft


class TestDraftQueue:
    def test_add_draft(self, tmp_path: pathlib.Path):
        queue = DraftQueue(tmp_path)
        draft = Draft(
            thread_id=342,
            thread_number=42,
            thread_title="NaN problem",
            thread_status="unanswered",
            question_type="project_help",
            project="Project 1",
            priority="high",
            content="The NaN values are expected...",
            context_used=["threads/s1/0142.md"],
            guardrails_applied="project1.md",
        )
        draft_id = queue.add(draft)
        assert draft_id is not None
        assert (tmp_path / f"{draft_id}.json").exists()

    def test_get_draft(self, tmp_path: pathlib.Path):
        queue = DraftQueue(tmp_path)
        draft = Draft(
            thread_id=100, thread_number=1, thread_title="Test",
            thread_status="unanswered", question_type="logistics",
            project=None, priority="high", content="Answer here.",
            context_used=[], guardrails_applied=None,
        )
        draft_id = queue.add(draft)
        loaded = queue.get(draft_id)
        assert loaded is not None
        assert loaded.thread_id == 100
        assert loaded.content == "Answer here."

    def test_list_drafts(self, tmp_path: pathlib.Path):
        queue = DraftQueue(tmp_path)
        for i in range(3):
            queue.add(Draft(
                thread_id=i, thread_number=i, thread_title=f"Thread {i}",
                thread_status="unanswered", question_type="logistics",
                project=None, priority="high", content=f"Answer {i}",
                context_used=[], guardrails_applied=None,
            ))
        drafts = queue.list()
        assert len(drafts) == 3

    def test_remove_draft(self, tmp_path: pathlib.Path):
        queue = DraftQueue(tmp_path)
        draft = Draft(
            thread_id=1, thread_number=1, thread_title="T",
            thread_status="unanswered", question_type="logistics",
            project=None, priority="high", content="A",
            context_used=[], guardrails_applied=None,
        )
        draft_id = queue.add(draft)
        queue.remove(draft_id)
        assert queue.get(draft_id) is None

    def test_list_filtered_by_project(self, tmp_path: pathlib.Path):
        queue = DraftQueue(tmp_path)
        queue.add(Draft(
            thread_id=1, thread_number=1, thread_title="T1",
            thread_status="unanswered", question_type="project_help",
            project="Project 1", priority="high", content="A1",
            context_used=[], guardrails_applied=None,
        ))
        queue.add(Draft(
            thread_id=2, thread_number=2, thread_title="T2",
            thread_status="unanswered", question_type="logistics",
            project=None, priority="medium", content="A2",
            context_used=[], guardrails_applied=None,
        ))
        filtered = queue.list(project="Project 1")
        assert len(filtered) == 1
        assert filtered[0].project == "Project 1"
