"""Configuration management for ed-bot."""

import pathlib
from dataclasses import dataclass, field

import yaml


@dataclass
class BotConfig:
    """ed-bot configuration loaded from ~/.ed-bot/config.yaml."""

    bot_dir: pathlib.Path
    course_id: int = 0
    region: str = "us"
    semesters: list[dict] = field(default_factory=list)
    data_dir: str = ""
    playbook_dir: str = ""
    draft_queue_dir: str = ""

    @classmethod
    def load(cls, bot_dir: pathlib.Path) -> "BotConfig":
        config_path = bot_dir / "config.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Config not found: {config_path}")
        data = yaml.safe_load(config_path.read_text())
        return cls(
            bot_dir=bot_dir,
            course_id=data.get("course_id", 0),
            region=data.get("region", "us"),
            semesters=data.get("semesters", []),
            data_dir=data.get("data_dir", str(bot_dir / "knowledge")),
            playbook_dir=data.get("playbook_dir", str(bot_dir / "playbook")),
            draft_queue_dir=data.get("draft_queue_dir", str(bot_dir / "drafts")),
        )

    def save(self) -> None:
        data = {
            "course_id": self.course_id,
            "region": self.region,
            "semesters": self.semesters,
            "data_dir": self.data_dir,
            "playbook_dir": self.playbook_dir,
            "draft_queue_dir": self.draft_queue_dir,
        }
        config_path = self.bot_dir / "config.yaml"
        config_path.write_text(yaml.dump(data, default_flow_style=False))

    @property
    def threads_dir(self) -> pathlib.Path:
        return pathlib.Path(self.data_dir) / "threads"

    @property
    def projects_dir(self) -> pathlib.Path:
        return pathlib.Path(self.data_dir) / "projects"

    @property
    def lectures_dir(self) -> pathlib.Path:
        return pathlib.Path(self.data_dir) / "lectures"

    @property
    def guardrails_dir(self) -> pathlib.Path:
        return pathlib.Path(self.playbook_dir) / "guardrails"

    @property
    def style_guide_path(self) -> pathlib.Path:
        return pathlib.Path(self.playbook_dir) / "style-guide.md"

    @property
    def drafts_dir(self) -> pathlib.Path:
        return pathlib.Path(self.draft_queue_dir)

    @property
    def state_dir(self) -> pathlib.Path:
        return self.bot_dir / "state"
