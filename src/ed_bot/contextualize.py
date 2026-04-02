"""Resumable context generation via Ollama for knowledge base files.

Generates 1-2 sentence context prefixes for each markdown file in the
knowledge base. Uses async HTTP to keep multiple requests in flight,
eliminating idle time between Ollama calls. Fully resumable — tracks
progress in a state file, safe to stop and restart.
"""

import asyncio
import json
import pathlib
import re
from datetime import datetime, timezone

import httpx
import yaml
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    MofNCompleteColumn,
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
    """Generates context strings for knowledge base files via Ollama. Resumable and async."""

    def __init__(
        self,
        knowledge_dir: pathlib.Path,
        state_dir: pathlib.Path,
        model: str = "llama3.2",
        ollama_url: str = "http://localhost:11434",
        concurrency: int = 8,
    ):
        self.knowledge_dir = pathlib.Path(knowledge_dir)
        self.state_dir = pathlib.Path(state_dir)
        self.model = model
        self.ollama_url = ollama_url
        self.concurrency = concurrency
        self._sync_client = httpx.Client(timeout=60.0)
        self._state_path = self.state_dir / "contextualize-progress.json"
        self._state = self._load_state()
        self._lock = None  # initialized in async context

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
        return rel_path in set(self._state["completed_files"])

    def _mark_completed(self, rel_path: str):
        self._state["completed_files"].append(rel_path)
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
        """Extract title, category, and content from a markdown file."""
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
                body = text[end_idx + 3:]

        if not title:
            match = re.search(r"^#\s+(.+)", body, re.MULTILINE)
            if match:
                title = match.group(1).strip()

        return title, category, body[:2000]

    async def _generate_context_async(
        self, client: httpx.AsyncClient, title: str, category: str, content: str
    ) -> str:
        """Call Ollama to generate context (async)."""
        prompt = CONTEXT_PROMPT.format(title=title, category=category, content=content)
        try:
            response = await client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 500,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            result = data.get("response", "").strip()
            if not result:
                thinking = data.get("thinking", "")
                if thinking:
                    result = thinking.strip()
            if "<think>" in result:
                result = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()
            if result and len(result) > 300:
                sentences = [s.strip() for s in result.split(".") if s.strip()]
                if len(sentences) > 2:
                    result = ". ".join(sentences[-2:]) + "."
            result = result.strip('"').strip("'")
            return result
        except Exception:
            return ""

    def _generate_context(self, title: str, category: str, content: str) -> str:
        """Call Ollama to generate context (sync, for single-file use)."""
        prompt = CONTEXT_PROMPT.format(title=title, category=category, content=content)
        try:
            response = self._sync_client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 500},
                },
            )
            response.raise_for_status()
            data = response.json()
            result = data.get("response", "").strip()
            if not result:
                thinking = data.get("thinking", "")
                if thinking:
                    result = thinking.strip()
            if "<think>" in result:
                result = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()
            if result and len(result) > 300:
                sentences = [s.strip() for s in result.split(".") if s.strip()]
                if len(sentences) > 2:
                    result = ". ".join(sentences[-2:]) + "."
            result = result.strip('"').strip("'")
            return result
        except Exception:
            return ""

    def _write_context_to_file(self, file_path: pathlib.Path, context: str):
        """Write context into the YAML frontmatter of a markdown file."""
        text = file_path.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            text = f'---\ncontext: "{context}"\n---\n{text}'
        else:
            end_idx = text.find("---", 3)
            if end_idx == -1:
                return
            safe_context = context.replace('"', '\\"')
            frontmatter = text[3:end_idx].rstrip()
            new_frontmatter = f'{frontmatter}\ncontext: "{safe_context}"\n'
            text = f"---\n{new_frontmatter}---{text[end_idx + 3:]}"
        file_path.write_text(text, encoding="utf-8")

    def is_ollama_available(self) -> bool:
        """Check if Ollama is running."""
        try:
            resp = self._sync_client.get(f"{self.ollama_url}/api/tags")
            resp.raise_for_status()
            return True
        except Exception:
            return False

    async def _process_file(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        file_path: pathlib.Path,
        progress,
        task_id,
    ) -> tuple[bool, bool]:
        """Process a single file. Returns (success, error)."""
        async with semaphore:
            rel = str(file_path.relative_to(self.knowledge_dir))
            try:
                title, category, content = self._extract_info(file_path)
                if not content.strip():
                    self._mark_completed(rel)
                    progress.advance(task_id)
                    return (False, False)

                context = await self._generate_context_async(client, title, category, content)
                if context:
                    self._write_context_to_file(file_path, context)
                    self._mark_completed(rel)
                    progress.advance(task_id)
                    return (True, False)
                else:
                    self._mark_completed(rel)
                    progress.advance(task_id)
                    return (False, True)
            except Exception as e:
                progress.console.print(f"[yellow]Error on {rel}: {e}[/yellow]")
                progress.advance(task_id)
                return (False, True)

    async def _run_async(self, to_process: list[pathlib.Path], progress, task_id) -> tuple[int, int]:
        """Run context generation with async concurrency."""
        semaphore = asyncio.Semaphore(self.concurrency)
        async with httpx.AsyncClient(timeout=60.0) as client:
            tasks = [
                self._process_file(client, semaphore, f, progress, task_id)
                for f in to_process
            ]
            results = await asyncio.gather(*tasks)

        processed = sum(1 for s, e in results if s)
        errors = sum(1 for s, e in results if e)
        return processed, errors

    def run(self, subdirs: list[str] | None = None, force: bool = False) -> dict:
        """Run context generation across all knowledge base files.

        Uses async concurrency to keep multiple Ollama requests in flight.
        Fully resumable — safe to stop and restart.
        """
        if not self.is_ollama_available():
            console.print("[red]Ollama is not running. Start it with: ollama serve[/red]")
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

        # Build a set for faster lookup
        completed_set = set(self._state["completed_files"])

        # Filter
        to_process = []
        skipped = 0
        for f in all_files:
            rel = str(f.relative_to(self.knowledge_dir))
            if not force and (rel in completed_set or self._has_context(f)):
                skipped += 1
                continue
            to_process.append(f)

        console.print(
            f"[bold]Found {len(all_files)} files, {skipped} already done, "
            f"{len(to_process)} to process (concurrency: {self.concurrency}).[/bold]"
        )

        if not to_process:
            console.print("[green]All files already have context.[/green]")
            return {"processed": 0, "skipped": skipped, "errors": 0}

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
            task_id = progress.add_task("Generating context", total=len(to_process))
            processed, errors = asyncio.run(
                self._run_async(to_process, progress, task_id)
            )

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
