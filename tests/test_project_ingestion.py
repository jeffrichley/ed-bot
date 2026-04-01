import pathlib
from ed_bot.ingestion.projects import ProjectIngester
from ed_bot.config import BotConfig


class TestProjectIngester:
    def test_ingest_python_file(self, tmp_bot_dir: pathlib.Path, fixtures_dir: pathlib.Path):
        config = BotConfig.load(tmp_bot_dir)
        ingester = ProjectIngester(config)

        py_file = fixtures_dir / "sample_projects" / "sample.py"
        count = ingester.ingest_code(py_file, project_name="Project 1")

        assert count == 1
        md_files = list(config.projects_dir.glob("*.md"))
        assert len(md_files) == 1
        content = md_files[0].read_text()
        assert "project:" in content
        assert "```python" in content
        assert "test_code" in content

    def test_ingest_code_directory(self, tmp_bot_dir: pathlib.Path, tmp_path: pathlib.Path):
        config = BotConfig.load(tmp_bot_dir)
        ingester = ProjectIngester(config)

        code_dir = tmp_path / "project_code"
        code_dir.mkdir()
        (code_dir / "main.py").write_text("def main(): pass")
        (code_dir / "helper.py").write_text("def helper(): pass")
        (code_dir / "notes.txt").write_text("not a python file")

        count = ingester.ingest_code(code_dir, project_name="Project 2")
        assert count == 2  # only .py files
