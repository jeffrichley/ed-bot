"""pyqmd collection management for ed-bot."""

import pathlib

from pyqmd import PyQMD

from ed_bot.config import BotConfig


class KnowledgeBase:
    """Manages pyqmd collections for ed-bot's knowledge base."""

    def __init__(self, config: BotConfig):
        self.config = config
        self.qmd = PyQMD(data_dir=str(config.bot_dir / "pyqmd"))

    def index_threads(self, semester: str, force: bool = False, observer=None) -> int:
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

        return self.qmd.index(collection_name, force=force, observer=observer)

    def index_projects(self, force: bool = False, observer=None) -> int:
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

        return self.qmd.index("projects", force=force, observer=observer)

    def index_lectures(self, force: bool = False, observer=None) -> int:
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

        return self.qmd.index("lectures", force=force, observer=observer)

    def index_canvas_pages(self, force: bool = False, observer=None) -> int:
        """Index Canvas course pages."""
        pages_dir = self.config.canvas_pages_dir
        if not pages_dir.exists():
            return 0

        try:
            self.qmd.add_collection(
                "canvas-pages",
                paths=[str(pages_dir)],
                mask="**/*.md",
            )
        except ValueError:
            pass

        return self.qmd.index("canvas-pages", force=force, observer=observer)

    def index_announcements(self, force: bool = False, observer=None) -> int:
        """Index Canvas announcements."""
        ann_dir = self.config.canvas_announcements_dir
        if not ann_dir.exists():
            return 0

        try:
            self.qmd.add_collection(
                "announcements",
                paths=[str(ann_dir)],
                mask="**/*.md",
            )
        except ValueError:
            pass

        return self.qmd.index("announcements", force=force, observer=observer)

    def index_all(self, force: bool = False) -> dict[str, int]:
        """Index everything. Returns dict of collection_name -> chunk_count."""
        from pyqmd.progress import RichProgressObserver

        results = {}
        observer = RichProgressObserver()

        # Thread semesters
        if self.config.threads_dir.exists():
            for semester_dir in sorted(self.config.threads_dir.iterdir()):
                if semester_dir.is_dir():
                    name = semester_dir.name
                    results[f"threads-{name}"] = self.index_threads(name, force=force, observer=observer)

        # Projects
        results["projects"] = self.index_projects(force=force, observer=observer)

        # Lectures
        results["lectures"] = self.index_lectures(force=force, observer=observer)

        # Canvas pages
        results["canvas-pages"] = self.index_canvas_pages(force=force, observer=observer)

        # Announcements
        results["announcements"] = self.index_announcements(force=force, observer=observer)

        return results

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
