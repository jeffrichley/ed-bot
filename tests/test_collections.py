import pathlib
from unittest.mock import MagicMock, patch
from ed_bot.knowledge.collections import KnowledgeBase
from ed_bot.config import BotConfig


class TestKnowledgeBase:
    def test_init_creates_pyqmd(self, tmp_bot_dir: pathlib.Path):
        config = BotConfig.load(tmp_bot_dir)
        kb = KnowledgeBase(config)
        assert kb.qmd is not None

    def test_index_threads(self, tmp_bot_dir: pathlib.Path):
        config = BotConfig.load(tmp_bot_dir)
        # Create a sample thread markdown file
        semester_dir = config.threads_dir / "spring-2026"
        semester_dir.mkdir(parents=True, exist_ok=True)
        (semester_dir / "0001-test.md").write_text(
            "---\ntitle: test\n---\n# Test\n\nContent here."
        )

        kb = KnowledgeBase(config)
        count = kb.index_threads("spring-2026")
        assert count > 0

    def test_index_projects(self, tmp_bot_dir: pathlib.Path):
        config = BotConfig.load(tmp_bot_dir)
        projects_dir = config.projects_dir
        projects_dir.mkdir(parents=True, exist_ok=True)
        (projects_dir / "project1.md").write_text(
            "---\nproject: P1\n---\n# Project 1\n\nRequirements."
        )

        kb = KnowledgeBase(config)
        count = kb.index_projects()
        assert count > 0
