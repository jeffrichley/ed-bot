"""pyqmd collection management for ed-bot."""

import pathlib

from pyqmd import PyQMD

from ed_bot.config import BotConfig


class KnowledgeBase:
    """Manages pyqmd collections for ed-bot's knowledge base."""

    def __init__(self, config: BotConfig):
        self.config = config
        self.qmd = PyQMD(data_dir=str(config.bot_dir / "pyqmd"))

    def index_threads(self, semester: str, force: bool = False) -> int:
        """Index thread markdown files for a semester."""
        semester_dir = self.config.threads_dir / semester
        if not semester_dir.exists():
            return 0

        collection_name = f"threads-{semester}"
        try:
            self.qmd.add_collection(
                collection_name,
                paths=[str(semester_dir)],
                mask="**/*.md",
            )
        except ValueError:
            pass  # already exists

        return self.qmd.index(collection_name, force=force)

    def index_projects(self, force: bool = False) -> int:
        """Index project markdown files."""
        projects_dir = self.config.projects_dir
        if not projects_dir.exists():
            return 0

        try:
            self.qmd.add_collection(
                "projects",
                paths=[str(projects_dir)],
                mask="**/*.md",
            )
        except ValueError:
            pass

        return self.qmd.index("projects", force=force)

    def index_lectures(self, force: bool = False) -> int:
        """Index lecture transcript markdown files."""
        lectures_dir = self.config.lectures_dir
        if not lectures_dir.exists():
            return 0

        try:
            self.qmd.add_collection(
                "lectures",
                paths=[str(lectures_dir)],
                mask="**/*.md",
            )
        except ValueError:
            pass

        return self.qmd.index("lectures", force=force)

    def search(self, query: str, top_k: int = 10, collections: list[str] | None = None):
        """Search across knowledge base collections."""
        if collections is None:
            collections = self.qmd.list_collections()
        if not collections:
            return []
        return self.qmd.search(query, collections=collections, top_k=top_k)

    def status(self) -> dict:
        """Get status of all collections."""
        collections = self.qmd.list_collections()
        result = {}
        for name in collections:
            result[name] = self.qmd.status(name)
        return result
