import pathlib
import json
from unittest.mock import MagicMock, patch
from ed_bot.ingestion.threads import ThreadIngester
from ed_bot.config import BotConfig


class TestThreadIngester:
    def _mock_thread(self, thread_id=100, number=1, title="Test"):
        thread = MagicMock()
        thread.id = thread_id
        thread.number = number
        thread.course_id = 54321
        thread.title = title
        thread.content = "<document version='2.0'><paragraph>Body</paragraph></document>"
        thread.type = "question"
        thread.category = "General"
        thread.subcategory = None
        thread.is_pinned = False
        thread.is_private = False
        thread.is_locked = False
        thread.is_endorsed = False
        thread.is_answered = False
        thread.is_staff_answered = False
        thread.is_student_answered = False
        thread.created_at = MagicMock(isoformat=MagicMock(return_value="2026-03-15T10:30:00+00:00"))
        thread.updated_at = MagicMock(isoformat=MagicMock(return_value="2026-03-16T14:22:00+00:00"))
        thread.author = MagicMock(role="student")
        thread.comments = []
        thread.users = {}
        thread.has_staff_response = False
        return thread

    def test_ingest_creates_markdown_files(self, tmp_bot_dir: pathlib.Path):
        config = BotConfig.load(tmp_bot_dir)
        mock_client = MagicMock()
        mock_detail = self._mock_thread()
        mock_client.threads.list_all.return_value = [self._mock_thread()]
        mock_client.threads.get.return_value = mock_detail

        ingester = ThreadIngester(config, mock_client)
        count = ingester.ingest(course_id=54321, semester="spring-2026")

        thread_dir = config.threads_dir / "spring-2026"
        md_files = list(thread_dir.glob("*.md"))
        assert len(md_files) == 1
        assert count == 1

    def test_ingest_writes_frontmatter(self, tmp_bot_dir: pathlib.Path):
        config = BotConfig.load(tmp_bot_dir)
        mock_client = MagicMock()
        mock_detail = self._mock_thread(title="NaN problem")
        mock_client.threads.list_all.return_value = [self._mock_thread(title="NaN problem")]
        mock_client.threads.get.return_value = mock_detail

        ingester = ThreadIngester(config, mock_client)
        ingester.ingest(course_id=54321, semester="spring-2026")

        thread_dir = config.threads_dir / "spring-2026"
        md_files = list(thread_dir.glob("*.md"))
        content = md_files[0].read_text()
        assert "thread_id:" in content
        assert "semester: spring-2026" in content

    def test_incremental_tracks_timestamps(self, tmp_bot_dir: pathlib.Path):
        config = BotConfig.load(tmp_bot_dir)
        mock_client = MagicMock()
        mock_client.threads.list_all.return_value = []

        ingester = ThreadIngester(config, mock_client)
        ingester.ingest(course_id=54321, semester="spring-2026")

        state_file = config.state_dir / "last-sync.json"
        assert state_file.exists()
