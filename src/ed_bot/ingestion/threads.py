"""Thread ingestion: fetch from EdStem, convert to markdown, write to disk."""

import json
import pathlib
from datetime import datetime, timezone

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn, MofNCompleteColumn

from ed_bot.config import BotConfig
from ed_bot.ingestion.markdown import CommentData, ThreadData, thread_filename, thread_to_markdown

console = Console()


class ThreadIngester:
    """Fetches threads from EdStem and writes structured markdown files."""

    def __init__(self, config: BotConfig, ed_client):
        self.config = config
        self.client = ed_client

    def ingest(self, course_id: int, semester: str, force: bool = False) -> int:
        """Ingest threads for a course/semester. Returns count of threads ingested.

        Only fetches threads updated since the last sync unless force=True.
        """
        output_dir = self.config.threads_dir / semester
        output_dir.mkdir(parents=True, exist_ok=True)

        last_sync = self._load_last_sync(semester)
        last_sync_dt = None
        if last_sync and not force:
            last_sync_dt = datetime.fromisoformat(last_sync)

        # Phase 1: Fetch thread listing (fast, paginated)
        console.print(f"[bold]Fetching thread list for {semester}...[/bold]")
        all_summaries = list(self.client.threads.list_all(course_id))
        console.print(f"  Found {len(all_summaries)} total threads.")

        # Filter to threads needing update
        if last_sync_dt:
            to_fetch = [t for t in all_summaries if not t.updated_at or t.updated_at > last_sync_dt]
            skipped = len(all_summaries) - len(to_fetch)
            if skipped > 0:
                console.print(f"  [dim]Skipping {skipped} unchanged threads.[/dim]")
        else:
            to_fetch = all_summaries
            skipped = 0

        if not to_fetch:
            console.print(f"  [green]Already up to date.[/green]")
            self._save_last_sync(semester)
            return 0

        console.print(f"  [bold]Downloading {len(to_fetch)} threads...[/bold]")

        # Phase 2: Fetch details with progress bar
        count = 0
        errors = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            MofNCompleteColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"Ingesting {semester}", total=len(to_fetch))

            for thread_summary in to_fetch:
                try:
                    thread_detail = self.client.threads.get(thread_summary.id)
                except Exception as e:
                    errors += 1
                    progress.console.print(
                        f"  [yellow]Warning: Failed to fetch #{thread_summary.number}: {e}[/yellow]"
                    )
                    progress.advance(task)
                    continue

                thread_data = self._convert_thread(thread_detail, semester)
                filename = thread_filename(thread_data.thread_number, thread_data.title)
                md_content = thread_to_markdown(thread_data)

                (output_dir / filename).write_text(md_content, encoding="utf-8")
                count += 1
                progress.advance(task)

        if errors > 0:
            console.print(f"  [yellow]{errors} threads failed to download.[/yellow]")

        self._save_last_sync(semester)
        return count

    def _convert_thread(self, detail, semester: str) -> ThreadData:
        """Convert an ed-api ThreadDetail to our ThreadData."""
        try:
            from ed_api.content import ed_xml_to_markdown
            _xml_converter = ed_xml_to_markdown
        except ImportError:
            _xml_converter = None

        def to_md(content: str) -> str:
            if _xml_converter is not None:
                try:
                    return _xml_converter(content)
                except Exception:
                    pass
            return content

        comments = []
        for c in getattr(detail, "comments", []):
            author = detail.users.get(c.user_id) if hasattr(detail, "users") else None
            role = author.role if author else "student"
            comments.append(CommentData(
                type=c.type,
                author_role=role,
                content=to_md(c.content),
                is_endorsed=c.is_endorsed,
            ))

        has_staff_response = False
        if hasattr(detail, "has_staff_response"):
            has_staff_response = detail.has_staff_response

        return ThreadData(
            thread_id=detail.id,
            thread_number=detail.number,
            course_id=detail.course_id,
            semester=semester,
            category=detail.category,
            subcategory=getattr(detail, "subcategory", None),
            type=detail.type,
            title=detail.title,
            content=to_md(detail.content),
            author_role=detail.author.role if detail.author else "student",
            is_endorsed=detail.is_endorsed,
            is_private=detail.is_private,
            is_answered=detail.is_answered,
            has_staff_response=has_staff_response,
            has_accepted_answer=getattr(detail, "is_answered", False),
            created=detail.created_at.isoformat() if detail.created_at else "",
            updated=detail.updated_at.isoformat() if detail.updated_at else "",
            comments=comments,
        )

    def _load_last_sync(self, semester: str) -> str | None:
        state_file = self.config.state_dir / "last-sync.json"
        if not state_file.exists():
            return None
        data = json.loads(state_file.read_text())
        return data.get(semester)

    def _save_last_sync(self, semester: str) -> None:
        state_file = self.config.state_dir / "last-sync.json"
        data = {}
        if state_file.exists():
            data = json.loads(state_file.read_text())
        data[semester] = datetime.now(timezone.utc).isoformat()
        state_file.write_text(json.dumps(data, indent=2))
