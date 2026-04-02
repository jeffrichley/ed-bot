import json
import pathlib
from unittest.mock import patch, MagicMock
from ed_bot.contextualize import ContextGenerator


class TestContextGenerator:
    def test_extract_info_with_frontmatter(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text('---\ntitle: "Test Thread"\ncategory: "Project 1"\n---\n\n# Test Thread\n\nSome content here.')
        gen = ContextGenerator(knowledge_dir=tmp_path, state_dir=tmp_path / "state")
        title, category, content = gen._extract_info(md)
        assert title == "Test Thread"
        assert category == "Project 1"
        assert "Some content" in content

    def test_extract_info_without_frontmatter(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text("# My Heading\n\nSome content here.")
        gen = ContextGenerator(knowledge_dir=tmp_path, state_dir=tmp_path / "state")
        title, category, content = gen._extract_info(md)
        assert title == "My Heading"

    def test_has_context_true(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text('---\ntitle: "Test"\ncontext: "Already has context"\n---\n\nContent.')
        gen = ContextGenerator(knowledge_dir=tmp_path, state_dir=tmp_path / "state")
        assert gen._has_context(md) is True

    def test_has_context_false(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text('---\ntitle: "Test"\n---\n\nContent.')
        gen = ContextGenerator(knowledge_dir=tmp_path, state_dir=tmp_path / "state")
        assert gen._has_context(md) is False

    def test_write_context_to_file(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text('---\ntitle: "Test"\n---\n\n# Test\n\nContent.')
        gen = ContextGenerator(knowledge_dir=tmp_path, state_dir=tmp_path / "state")
        gen._write_context_to_file(md, "This is about testing.")
        result = md.read_text()
        assert 'context: "This is about testing."' in result
        assert "# Test" in result
        assert "Content." in result

    def test_state_persistence(self, tmp_path):
        gen = ContextGenerator(knowledge_dir=tmp_path, state_dir=tmp_path / "state")
        gen._mark_completed("file1.md")
        gen._mark_completed("file2.md")
        gen._save_state()

        gen2 = ContextGenerator(knowledge_dir=tmp_path, state_dir=tmp_path / "state")
        assert gen2._is_completed("file1.md")
        assert gen2._is_completed("file2.md")
        assert not gen2._is_completed("file3.md")

    def test_skips_completed_files(self, tmp_path):
        md1 = tmp_path / "done.md"
        md1.write_text('---\ntitle: "Done"\ncontext: "Already done"\n---\n\nContent.')
        md2 = tmp_path / "new.md"
        md2.write_text('---\ntitle: "New"\n---\n\nContent.')

        gen = ContextGenerator(knowledge_dir=tmp_path, state_dir=tmp_path / "state")
        # Mock Ollama as available but return empty context (simulates generation)
        gen.is_ollama_available = lambda: True
        gen._generate_context = lambda *args: "Generated context"
        results = gen.run()
        assert results["skipped"] == 1  # the one with existing context
        assert results["processed"] == 1  # the new one got processed
