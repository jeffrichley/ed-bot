"""Canvas assignment ingestion: pull project requirements from Canvas API."""

import os
import pathlib
import re
from datetime import datetime, timezone

import httpx
from markdownify import markdownify as html_to_md
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn, TimeElapsedColumn

from ed_bot.config import BotConfig

console = Console()


class CanvasIngester:
    """Pulls assignment descriptions from Canvas and converts to markdown."""

    def __init__(self, config: BotConfig):
        self.config = config
        self._token = os.environ.get("CANVAS_API_TOKEN")
        self._base_url = os.environ.get("CANVAS_BASE_URL", "https://gatech.instructure.com")
        if not self._token:
            raise ValueError(
                "CANVAS_API_TOKEN not set. Add it to your .env file. "
                "Get a token at Canvas > Account > Settings > New Access Token."
            )
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=30.0,
        )

    def ingest_assignments(
        self,
        canvas_course_id: int,
        filter_prefix: str | None = "Project",
    ) -> int:
        """Pull assignments from Canvas and save as markdown.

        Args:
            canvas_course_id: Canvas course ID (from URL)
            filter_prefix: Only ingest assignments whose name starts with this.
                          Set to None to ingest all.

        Returns count of assignments ingested.
        """
        console.print(f"[bold]Fetching assignments from Canvas course {canvas_course_id}...[/bold]")

        assignments = self._fetch_assignments(canvas_course_id)

        if filter_prefix:
            assignments = [a for a in assignments if a["name"].startswith(filter_prefix)]

        console.print(f"  Found {len(assignments)} assignments to ingest.")

        if not assignments:
            return 0

        output_dir = self.config.projects_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Ingesting assignments", total=len(assignments))

            for assignment in assignments:
                name = assignment["name"]
                description_html = assignment.get("description", "") or ""

                if not description_html.strip():
                    progress.advance(task)
                    continue

                # Convert HTML to markdown
                md_content = html_to_md(description_html, heading_style="ATX")

                # Build frontmatter
                slug = _slugify(name)
                due_at = assignment.get("due_at", "")
                points = assignment.get("points_possible", 0)
                canvas_url = assignment.get("html_url", "")

                frontmatter = f"""---
project: "{name}"
type: requirements
source: canvas
canvas_course_id: {canvas_course_id}
canvas_assignment_id: {assignment['id']}
canvas_url: "{canvas_url}"
points_possible: {points}
due_at: "{due_at or ''}"
ingested: {datetime.now(timezone.utc).isoformat()}
---"""

                full_content = f"{frontmatter}\n\n# {name}\n\n{md_content}\n"

                filename = f"{slug}.md"
                (output_dir / filename).write_text(full_content, encoding="utf-8")
                count += 1
                progress.advance(task)

        return count

    def _fetch_assignments(self, canvas_course_id: int) -> list[dict]:
        """Fetch all assignments from Canvas API (handles pagination)."""
        assignments = []
        url = f"{self._base_url}/api/v1/courses/{canvas_course_id}/assignments"
        params = {"per_page": 100, "order_by": "position"}

        while url:
            resp = self._client.get(url, params=params)
            resp.raise_for_status()
            assignments.extend(resp.json())

            # Canvas pagination via Link header
            link_header = resp.headers.get("Link", "")
            url = None
            params = None  # params are in the next URL
            for part in link_header.split(","):
                if 'rel="next"' in part:
                    url = part.split(";")[0].strip().strip("<>")
                    break

        return assignments

    def list_assignments(self, canvas_course_id: int) -> list[dict]:
        """List assignments (for preview before ingesting)."""
        assignments = self._fetch_assignments(canvas_course_id)
        return [
            {
                "id": a["id"],
                "name": a["name"],
                "points": a.get("points_possible", 0),
                "due_at": a.get("due_at", ""),
                "desc_length": len(a.get("description", "") or ""),
            }
            for a in assignments
        ]


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]
