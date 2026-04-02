"""Resumable context generation via Ollama for knowledge base files."""

import json
import pathlib
import re
from datetime import datetime, timezone

import httpx
import yaml
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

console = Console()

CONTEXT_PROMPT = """You are generating a search context for a document in a course Q&A knowledge base. Given the document title and content below, write 1-2 concise sentences that describe what this document is about. Focus on the specific topic, project, and type of question. Do not use phrases like "This document" — just state what it covers.

Title: {title}
Category: {category}

Content:
{content}

Context:"""


class ContextGenerator:
    """Generates context strings for knowledge base files via Ollama. Resumable."""

    def __init__(
        self,
        knowledge_dir: pathlib.Path,
        state_dir: pathlib.Path,
        model: str = "qwen3.5:9b",
        ollama_url: str = "http://localhost:11434",
    ):
        self.knowledge_dir = pathlib.Path(knowledge_dir)
        self.state_dir = pathlib.Path(state_dir)
        self.model = model
        self.ollama_url = ollama_url
        self._client = httpx.Client(timeout=60.0)
        self._state_path = self.state_dir / "contextualize-progress.json"
        self._state = self._load_state()

    def _load_state(self) -> dict:
        if self._state_path.exists():
            return json.loads(self._state_path.read_text())
        return {
            "completed_files": [],
            "model": self.model,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    def _save_state(self):
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._state["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._state_path.write_text(json.dumps(self._state, indent=2))

    def _is_completed(self, rel_path: str) -> bool:
        return rel_path in self._state["completed_files"]

    def _mark_completed(self, rel_path: str):
        self._state["completed_files"].append(rel_path)
        # Save every 10 files for efficiency
        if len(self._state["completed_files"]) % 10 == 0:
            self._save_state()

    def _has_context(self, file_path: pathlib.Path) -> bool:
        """Check if file already has context in frontmatter."""
        text = file_path.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            return False
        end_idx = text.find("---", 3)
        if end_idx == -1:
            return False
        frontmatter = text[3:end_idx]
        return "context:" in frontmatter

    def _extract_info(self, file_path: pathlib.Path) -> tuple[str, str, str]:
        """Extract title, category, and content from a markdown file.
        Returns (title, category, content_preview).
        """
        text = file_path.read_text(encoding="utf-8", errors="replace")
        title = ""
        category = ""
        body = text

        if text.startswith("---"):
            end_idx = text.find("---", 3)
            if end_idx != -1:
                try:
                    fm = yaml.safe_load(text[3:end_idx])
                    if isinstance(fm, dict):
                        title = fm.get("title", "") or fm.get("lecture", "") or ""
                        category = fm.get("category", "") or fm.get("type", "") or ""
                except Exception:
                    pass
                body = text[end_idx + 3 :]

        if not title:
            # Try first heading
            match = re.search(r"^#\s+(.+)", body, re.MULTILINE)
            if match:
                title = match.group(1).strip()

        return title, category, body[:2000]

    def _generate_context(self, title: str, category: str, content: str) -> str:
        """Call Ollama to generate context."""
        prompt = CONTEXT_PROMPT.format(
            title=title,
            category=category,
            content=content,
        )
        try:
            response = self._client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 100,
                    },
                },
            )
            response.raise_for_status()
            result = response.json().get("response", "").strip()
            # Clean thinking tags (qwen3 sometimes adds these)
            if "<think>" in result:
                result = re.sub(
                    r"<think>.*?</think>", "", result, flags=re.DOTALL
                ).strip()
            # Clean up quotes if the model wraps in them
            result = result.strip('"').strip("'")
            return result
        except Exception as e:
            console.print(f"[yellow]Ollama error: {e}[/yellow]")
            return ""

    def _write_context_to_file(self, file_path: pathlib.Path, context: str):
        """Write context into the YAML frontmatter of a markdown file."""
        text = file_path.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            # No frontmatter — add it
            text = f'---\ncontext: "{context}"\n---\n{text}'
        else:
            end_idx = text.find("---", 3)
            if end_idx == -1:
                return
            # Insert context before closing ---
            # Escape quotes in context for YAML
            safe_context = context.replace('"', '\\"')
            frontmatter = text[3:end_idx].rstrip()
            new_frontmatter = f'{frontmatter}\ncontext: "{safe_context}"\n'
            text = f"---\n{new_frontmatter}---{text[end_idx + 3 :]}"

        file_path.write_text(text, encoding="utf-8")

    def is_ollama_available(self) -> bool:
        """Check if Ollama is running."""
        try:
            resp = self._client.get(f"{self.ollama_url}/api/tags")
            resp.raise_for_status()
            return True
        except Exception:
            return False

    def run(self, subdirs: list[str] | None = None, force: bool = False) -> dict:
        """Run context generation across all knowledge base files.

        Args:
            subdirs: Specific subdirectories to process (e.g., ["threads", "projects"]).
                    None means all.
            force: If True, regenerate context even for files that already have it.

        Returns dict with counts: {"processed": N, "skipped": N, "errors": N}
        """
        if not self.is_ollama_available():
            console.print(
                "[red]Ollama is not running. Start it with: ollama serve[/red]"
            )
            return {"processed": 0, "skipped": 0, "errors": 0}

        # Collect all markdown files
        all_files = []
        if subdirs:
            for subdir in subdirs:
                d = self.knowledge_dir / subdir
                if d.exists():
                    all_files.extend(sorted(d.rglob("*.md")))
        else:
            all_files = sorted(self.knowledge_dir.rglob("*.md"))

        # Filter
        to_process = []
        skipped = 0
        for f in all_files:
            rel = str(f.relative_to(self.knowledge_dir))
            if not force and (self._is_completed(rel) or self._has_context(f)):
                skipped += 1
                continue
            to_process.append(f)

        console.print(
            f"[bold]Found {len(all_files)} files, {skipped} already done, "
            f"{len(to_process)} to process.[/bold]"
        )

        if not to_process:
            console.print("[green]All files already have context.[/green]")
            return {"processed": 0, "skipped": skipped, "errors": 0}

        processed = 0
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
            task = progress.add_task("Generating context", total=len(to_process))

            for file_path in to_process:
                rel = str(file_path.relative_to(self.knowledge_dir))
                try:
                    title, category, content = self._extract_info(file_path)
                    if not content.strip():
                        self._mark_completed(rel)
                        progress.advance(task)
                        continue

                    context = self._generate_context(title, category, content)
                    if context:
                        self._write_context_to_file(file_path, context)
                        processed += 1
                    else:
                        errors += 1

                    self._mark_completed(rel)
                except Exception as e:
                    progress.console.print(f"[yellow]Error on {rel}: {e}[/yellow]")
                    errors += 1

                progress.advance(task)

        self._save_state()
        return {"processed": processed, "skipped": skipped, "errors": errors}

    def status(self) -> dict:
        """Report progress."""
        all_files = list(self.knowledge_dir.rglob("*.md"))
        completed = len(self._state["completed_files"])
        with_context = sum(1 for f in all_files if self._has_context(f))
        return {
            "total_files": len(all_files),
            "completed_in_state": completed,
            "files_with_context": with_context,
            "model": self._state.get("model", "unknown"),
            "started_at": self._state.get("started_at", ""),
            "last_updated": self._state.get("last_updated", ""),
        }
