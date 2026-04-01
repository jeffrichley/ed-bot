"""Shared test fixtures for ed-bot."""

import pathlib
import pytest
import yaml

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> pathlib.Path:
    return FIXTURES_DIR


@pytest.fixture
def sample_playbook_dir() -> pathlib.Path:
    return FIXTURES_DIR / "sample_playbook"


@pytest.fixture
def tmp_bot_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a temporary ed-bot data directory with default structure."""
    bot_dir = tmp_path / ".ed-bot"
    (bot_dir / "knowledge" / "threads").mkdir(parents=True)
    (bot_dir / "knowledge" / "projects").mkdir(parents=True)
    (bot_dir / "knowledge" / "lectures").mkdir(parents=True)
    (bot_dir / "playbook" / "guardrails").mkdir(parents=True)
    (bot_dir / "drafts").mkdir(parents=True)
    (bot_dir / "state").mkdir(parents=True)

    config = {
        "course_id": 54321,
        "region": "us",
        "semesters": [
            {"name": "spring-2026", "course_id": 54321},
        ],
        "data_dir": str(bot_dir / "knowledge"),
        "playbook_dir": str(bot_dir / "playbook"),
        "draft_queue_dir": str(bot_dir / "drafts"),
    }
    (bot_dir / "config.yaml").write_text(yaml.dump(config))
    return bot_dir
