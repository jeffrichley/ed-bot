import pathlib
import pytest
from ed_bot.config import BotConfig


class TestBotConfig:
    def test_load_from_yaml(self, tmp_bot_dir: pathlib.Path):
        config = BotConfig.load(tmp_bot_dir)
        assert config.course_id == 54321
        assert config.region == "us"
        assert len(config.semesters) == 1
        assert config.semesters[0]["name"] == "spring-2026"

    def test_load_nonexistent_raises(self, tmp_path: pathlib.Path):
        with pytest.raises(FileNotFoundError):
            BotConfig.load(tmp_path / "nope")

    def test_data_dir(self, tmp_bot_dir: pathlib.Path):
        config = BotConfig.load(tmp_bot_dir)
        assert pathlib.Path(config.data_dir).exists()

    def test_playbook_dir(self, tmp_bot_dir: pathlib.Path):
        config = BotConfig.load(tmp_bot_dir)
        assert pathlib.Path(config.playbook_dir).exists()

    def test_save(self, tmp_bot_dir: pathlib.Path):
        config = BotConfig.load(tmp_bot_dir)
        config.course_id = 99999
        config.save()
        reloaded = BotConfig.load(tmp_bot_dir)
        assert reloaded.course_id == 99999
