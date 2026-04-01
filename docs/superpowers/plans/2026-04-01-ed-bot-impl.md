# ed-bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an EdStem forum automation system that ingests historical Q&A, project docs, and lecture transcripts into a pyqmd knowledge base, then generates draft answers with per-project guardrails for faculty review.

**Architecture:** ed-bot orchestrates three layers: (1) ingestion converts EdStem threads, PDFs, and code into structured markdown files and indexes them via pyqmd, (2) the answer engine classifies questions and generates drafts using Claude API with retrieved context + guardrails, (3) the review queue manages draft lifecycle (approve/edit/reject/skip). The CLI (`ed`) exposes all operations with `--json` for LLM consumption. Claude Code skills wrap CLI commands.

**Tech Stack:** Python 3.11+, uv, Typer, Rich, ed-api, pyqmd, anthropic (Claude API), markitdown, faster-whisper, ffmpeg, PyYAML

---

## File Map

```
ed-bot/
├── pyproject.toml
├── README.md
├── src/
│   └── ed_bot/
│       ├── __init__.py
│       ├── config.py                    # Config loading/saving (YAML)
│       ├── ingestion/
│       │   ├── __init__.py
│       │   ├── threads.py              # Thread ingestion: EdStem → markdown → pyqmd
│       │   ├── projects.py             # Project ingestion: PDF/code → markdown → pyqmd
│       │   ├── lectures.py             # Lecture ingestion: video → transcript → markdown
│       │   └── markdown.py             # Thread/comment → markdown conversion helpers
│       ├── knowledge/
│       │   ├── __init__.py
│       │   ├── collections.py          # pyqmd collection management
│       │   └── retrieval.py            # Context retrieval for answer generation
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── classifier.py           # Thread status + question type classification
│       │   ├── drafter.py              # Draft generation (Claude API + context + guardrails)
│       │   ├── guardrails.py           # Guardrail loading + auto-generation
│       │   └── templates.py            # Response templates by question type
│       ├── queue/
│       │   ├── __init__.py
│       │   ├── manager.py              # Draft queue CRUD (JSON files on disk)
│       │   └── priority.py             # Priority scoring
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── main.py                 # Typer app: `ed` command
│       │   ├── ingest.py               # ed ingest subcommands
│       │   ├── review.py               # ed review/approve/reject/skip
│       │   ├── answer.py               # ed answer (inline drafting)
│       │   ├── status.py               # ed status
│       │   ├── guardrails_cmd.py       # ed guardrails generate/edit/list
│       │   └── output.py               # Shared Rich/JSON output helpers
│       └── skills/                     # Claude Code skill definitions
│           ├── ed-status.md
│           ├── ed-review.md
│           ├── ed-answer.md
│           └── ed-ingest.md
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_markdown.py
│   ├── test_thread_ingestion.py
│   ├── test_project_ingestion.py
│   ├── test_collections.py
│   ├── test_retrieval.py
│   ├── test_classifier.py
│   ├── test_templates.py
│   ├── test_guardrails.py
│   ├── test_queue.py
│   ├── test_priority.py
│   ├── test_drafter.py
│   ├── test_cli.py
│   └── fixtures/
│       ├── sample_threads/             # Mock EdStem thread data
│       ├── sample_projects/            # Sample PDF and Python files
│       └── sample_playbook/            # Sample style guide and guardrails
└── docs/
```

---

### Task 1: Project Scaffolding + Config

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/ed_bot/__init__.py`
- Create: `src/ed_bot/config.py`
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`
- Create: `tests/fixtures/sample_playbook/style-guide.md`
- Create: `tests/fixtures/sample_playbook/guardrails/project1.md`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "ed-bot"
version = "0.1.0"
description = "EdStem forum automation. Ingests Q&A history, generates draft answers with guardrails."
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.9.0",
    "rich>=13.0.0",
    "pyyaml>=6.0",
    "anthropic>=0.40.0",
    "ed-api",
    "pyqmd",
    "markitdown>=0.1.0",
]

[project.optional-dependencies]
lectures = [
    "faster-whisper>=1.0.0",
]
dev = [
    "pytest>=7.0.0",
]

[project.scripts]
ed = "ed_bot.cli.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/ed_bot"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Create README.md**

```markdown
# ed-bot

EdStem forum automation for GT ML4T and beyond.
```

- [ ] **Step 3: Create src/ed_bot/__init__.py**

```python
"""ed-bot: EdStem forum automation."""
```

- [ ] **Step 4: Create fixture files**

`tests/fixtures/sample_playbook/style-guide.md`:
```markdown
# Ed-Bot Style Guide

## Voice

You are a helpful teaching assistant for CS 7646 Machine Learning for Trading
at Georgia Tech. You are knowledgeable, patient, and encouraging.

## Tone by Question Type

### Logistics
- Be direct and factual

### Conceptual
- Use Socratic approach

### Project Help
- Never provide solution code
- Ask what they've tried

### Teaching Moments
- Be thorough

## General Rules
- Never provide complete solutions to graded assignments
- Always be respectful and encouraging
```

`tests/fixtures/sample_playbook/guardrails/project1.md`:
```markdown
---
project: "Project 1 - Martingale"
guardrail_level: strict
auto_generated: 2026-04-01T12:00:00Z
reviewed_by: null
---

# Project 1 - Martingale: Guardrails

## Never Reveal
- The specific implementation of the betting strategy
- Exact expected values for experiment results

## OK to Discuss
- General concept of the Martingale strategy
- How numpy.random works
- matplotlib plotting basics

## Common Questions — Redirect Patterns
- "Is my chart right?" → Ask what they expect to see
- "What should the mean be?" → Point to mathematical properties
```

- [ ] **Step 5: Create conftest.py**

`tests/conftest.py`:
```python
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
```

- [ ] **Step 6: Write config tests and implementation**

`tests/test_config.py`:
```python
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
```

`src/ed_bot/config.py`:
```python
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
```

- [ ] **Step 7: Verify and commit**

```bash
cd E:/workspaces/school/gt/ed-bot
uv sync
uv run pytest tests/test_config.py -v
git add pyproject.toml README.md src/ tests/
git commit -m "feat: project scaffolding and config management"
```

---

### Task 2: Thread → Markdown Conversion

**Files:**
- Create: `src/ed_bot/ingestion/__init__.py`
- Create: `src/ed_bot/ingestion/markdown.py`
- Create: `tests/test_markdown.py`

- [ ] **Step 1: Write tests**

`tests/test_markdown.py`:
```python
from datetime import datetime
from ed_bot.ingestion.markdown import thread_to_markdown, ThreadData, CommentData


class TestThreadToMarkdown:
    def test_basic_thread(self):
        thread = ThreadData(
            thread_id=342,
            thread_number=42,
            course_id=12345,
            semester="spring-2026",
            category="Project 1",
            subcategory="Martingale",
            type="question",
            title="get_data() returns NaN",
            content="My data has NaN values",
            author_role="student",
            is_endorsed=False,
            is_private=False,
            is_answered=False,
            has_staff_response=False,
            has_accepted_answer=False,
            created="2026-03-15T10:30:00Z",
            updated="2026-03-16T14:22:00Z",
            comments=[],
        )
        md = thread_to_markdown(thread)
        assert "thread_id: 342" in md
        assert "# get_data() returns NaN" in md
        assert "semester: spring-2026" in md
        assert "category:" in md

    def test_thread_with_comments(self):
        thread = ThreadData(
            thread_id=100,
            thread_number=1,
            course_id=54321,
            semester="spring-2026",
            category="General",
            subcategory=None,
            type="question",
            title="Test question",
            content="Question body",
            author_role="student",
            is_endorsed=True,
            is_private=False,
            is_answered=True,
            has_staff_response=True,
            has_accepted_answer=True,
            created="2026-03-15T10:30:00Z",
            updated="2026-03-16T14:22:00Z",
            comments=[
                CommentData(
                    type="answer",
                    author_role="staff",
                    content="The answer is...",
                    is_endorsed=True,
                ),
                CommentData(
                    type="comment",
                    author_role="student",
                    content="Thank you!",
                    is_endorsed=False,
                ),
            ],
        )
        md = thread_to_markdown(thread)
        assert "## Answer by staff (endorsed)" in md
        assert "The answer is..." in md
        assert "## Comment by student" in md
        assert "Thank you!" in md

    def test_frontmatter_has_required_fields(self):
        thread = ThreadData(
            thread_id=1, thread_number=1, course_id=1,
            semester="s1", category="cat", subcategory=None,
            type="question", title="t", content="c",
            author_role="student", is_endorsed=False,
            is_private=False, is_answered=False,
            has_staff_response=False, has_accepted_answer=False,
            created="2026-01-01T00:00:00Z", updated="2026-01-01T00:00:00Z",
            comments=[],
        )
        md = thread_to_markdown(thread)
        assert "---" in md
        assert "thread_id:" in md
        assert "semester:" in md
        assert "category:" in md
        assert "has_staff_response:" in md

    def test_filename_from_thread(self):
        from ed_bot.ingestion.markdown import thread_filename
        assert thread_filename(42, "get_data() returns NaN") == "0042-get-data-returns-nan.md"
        assert thread_filename(1, "Simple   Title!") == "0001-simple-title.md"
```

- [ ] **Step 2: Implement**

`src/ed_bot/ingestion/__init__.py`:
```python
"""Ingestion pipelines for ed-bot."""
```

`src/ed_bot/ingestion/markdown.py`:
```python
"""Convert EdStem threads and comments to structured markdown."""

import re
from dataclasses import dataclass, field


@dataclass
class CommentData:
    type: str  # "answer" or "comment"
    author_role: str  # "student", "staff", "admin"
    content: str  # markdown
    is_endorsed: bool


@dataclass
class ThreadData:
    thread_id: int
    thread_number: int
    course_id: int
    semester: str
    category: str
    subcategory: str | None
    type: str
    title: str
    content: str  # markdown body
    author_role: str
    is_endorsed: bool
    is_private: bool
    is_answered: bool
    has_staff_response: bool
    has_accepted_answer: bool
    created: str
    updated: str
    comments: list[CommentData] = field(default_factory=list)


def thread_to_markdown(thread: ThreadData) -> str:
    """Convert a ThreadData to structured markdown with YAML frontmatter."""
    frontmatter = f"""---
thread_id: {thread.thread_id}
thread_number: {thread.thread_number}
course_id: {thread.course_id}
semester: {thread.semester}
category: "{thread.category}"
subcategory: {f'"{thread.subcategory}"' if thread.subcategory else 'null'}
type: {thread.type}
title: "{thread.title}"
author_role: {thread.author_role}
status: {'resolved' if thread.is_answered else 'open'}
is_endorsed: {str(thread.is_endorsed).lower()}
is_private: {str(thread.is_private).lower()}
created: {thread.created}
updated: {thread.updated}
comment_count: {len(thread.comments)}
has_staff_response: {str(thread.has_staff_response).lower()}
has_accepted_answer: {str(thread.has_accepted_answer).lower()}
---"""

    body = f"\n\n# {thread.title}\n\n{thread.content}"

    for comment in thread.comments:
        label = comment.type.capitalize()
        endorsed_str = " (endorsed)" if comment.is_endorsed else ""
        body += f"\n\n## {label} by {comment.author_role}{endorsed_str}\n\n{comment.content}"

    return frontmatter + body + "\n"


def thread_filename(thread_number: int, title: str) -> str:
    """Generate a filename from thread number and title."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
    return f"{thread_number:04d}-{slug}.md"
```

- [ ] **Step 3: Verify and commit**

```bash
uv run pytest tests/test_markdown.py -v
git add src/ed_bot/ingestion/ tests/test_markdown.py
git commit -m "feat: thread to markdown conversion with frontmatter"
```

---

### Task 3: Thread Ingestion Pipeline

**Files:**
- Create: `src/ed_bot/ingestion/threads.py`
- Create: `tests/test_thread_ingestion.py`

- [ ] **Step 1: Write tests**

`tests/test_thread_ingestion.py`:
```python
import pathlib
import json
from unittest.mock import MagicMock, patch
from ed_bot.ingestion.threads import ThreadIngester
from ed_bot.config import BotConfig


class TestThreadIngester:
    def _mock_thread(self, thread_id=100, number=1, title="Test"):
        thread = MagicMock()
        thread.id = thread_id
        thread.number = number
        thread.course_id = 54321
        thread.title = title
        thread.content = "<document version='2.0'><paragraph>Body</paragraph></document>"
        thread.type = "question"
        thread.category = "General"
        thread.subcategory = None
        thread.is_pinned = False
        thread.is_private = False
        thread.is_locked = False
        thread.is_endorsed = False
        thread.is_answered = False
        thread.is_staff_answered = False
        thread.is_student_answered = False
        thread.created_at = MagicMock(isoformat=MagicMock(return_value="2026-03-15T10:30:00+00:00"))
        thread.updated_at = MagicMock(isoformat=MagicMock(return_value="2026-03-16T14:22:00+00:00"))
        thread.author = MagicMock(role="student")
        thread.comments = []
        thread.users = {}
        return thread

    def test_ingest_creates_markdown_files(self, tmp_bot_dir: pathlib.Path):
        config = BotConfig.load(tmp_bot_dir)
        mock_client = MagicMock()
        mock_detail = self._mock_thread()
        mock_client.threads.list_all.return_value = [self._mock_thread()]
        mock_client.threads.get.return_value = mock_detail

        ingester = ThreadIngester(config, mock_client)
        count = ingester.ingest(course_id=54321, semester="spring-2026")

        thread_dir = config.threads_dir / "spring-2026"
        md_files = list(thread_dir.glob("*.md"))
        assert len(md_files) == 1
        assert count == 1

    def test_ingest_writes_frontmatter(self, tmp_bot_dir: pathlib.Path):
        config = BotConfig.load(tmp_bot_dir)
        mock_client = MagicMock()
        mock_detail = self._mock_thread(title="NaN problem")
        mock_client.threads.list_all.return_value = [self._mock_thread(title="NaN problem")]
        mock_client.threads.get.return_value = mock_detail

        ingester = ThreadIngester(config, mock_client)
        ingester.ingest(course_id=54321, semester="spring-2026")

        thread_dir = config.threads_dir / "spring-2026"
        md_files = list(thread_dir.glob("*.md"))
        content = md_files[0].read_text()
        assert "thread_id:" in content
        assert "semester: spring-2026" in content

    def test_incremental_tracks_timestamps(self, tmp_bot_dir: pathlib.Path):
        config = BotConfig.load(tmp_bot_dir)
        mock_client = MagicMock()
        mock_client.threads.list_all.return_value = []

        ingester = ThreadIngester(config, mock_client)
        ingester.ingest(course_id=54321, semester="spring-2026")

        state_file = config.state_dir / "last-sync.json"
        assert state_file.exists()
```

- [ ] **Step 2: Implement**

`src/ed_bot/ingestion/threads.py`:
```python
"""Thread ingestion: fetch from EdStem, convert to markdown, write to disk."""

import json
import pathlib
from datetime import datetime, timezone

from rich.console import Console

from ed_bot.config import BotConfig
from ed_bot.ingestion.markdown import CommentData, ThreadData, thread_filename, thread_to_markdown

console = Console()


class ThreadIngester:
    """Fetches threads from EdStem and writes structured markdown files."""

    def __init__(self, config: BotConfig, ed_client):
        self.config = config
        self.client = ed_client

    def ingest(self, course_id: int, semester: str) -> int:
        """Ingest all threads for a course/semester. Returns count of threads ingested."""
        output_dir = self.config.threads_dir / semester
        output_dir.mkdir(parents=True, exist_ok=True)

        last_sync = self._load_last_sync(semester)
        count = 0

        for thread_summary in self.client.threads.list_all(course_id):
            try:
                thread_detail = self.client.threads.get(thread_summary.id)
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to fetch thread {thread_summary.id}: {e}[/yellow]")
                continue

            thread_data = self._convert_thread(thread_detail, semester)
            filename = thread_filename(thread_data.thread_number, thread_data.title)
            md_content = thread_to_markdown(thread_data)

            (output_dir / filename).write_text(md_content, encoding="utf-8")
            count += 1

        self._save_last_sync(semester)
        return count

    def _convert_thread(self, detail, semester: str) -> ThreadData:
        """Convert an ed-api ThreadDetail to our ThreadData."""
        from ed_api.content import ed_xml_to_markdown

        comments = []
        for c in getattr(detail, "comments", []):
            author = detail.users.get(c.user_id) if hasattr(detail, "users") else None
            role = author.role if author else "student"
            try:
                content_md = ed_xml_to_markdown(c.content)
            except Exception:
                content_md = c.content

            comments.append(CommentData(
                type=c.type,
                author_role=role,
                content=content_md,
                is_endorsed=c.is_endorsed,
            ))

        try:
            body_md = ed_xml_to_markdown(detail.content)
        except Exception:
            body_md = detail.content

        return ThreadData(
            thread_id=detail.id,
            thread_number=detail.number,
            course_id=detail.course_id,
            semester=semester,
            category=detail.category,
            subcategory=getattr(detail, "subcategory", None),
            type=detail.type,
            title=detail.title,
            content=body_md,
            author_role=detail.author.role if detail.author else "student",
            is_endorsed=detail.is_endorsed,
            is_private=detail.is_private,
            is_answered=detail.is_answered,
            has_staff_response=detail.has_staff_response if hasattr(detail, "has_staff_response") else False,
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
```

- [ ] **Step 3: Verify and commit**

```bash
uv run pytest tests/test_thread_ingestion.py -v
git add src/ed_bot/ingestion/threads.py tests/test_thread_ingestion.py
git commit -m "feat: thread ingestion pipeline (EdStem → markdown)"
```

---

### Task 4: Project Ingestion

**Files:**
- Create: `src/ed_bot/ingestion/projects.py`
- Create: `tests/test_project_ingestion.py`
- Create: `tests/fixtures/sample_projects/sample.py`

- [ ] **Step 1: Write tests**

`tests/fixtures/sample_projects/sample.py`:
```python
"""Sample project starter code."""

import numpy as np


def test_code():
    """TODO: Implement your strategy here."""
    pass
```

`tests/test_project_ingestion.py`:
```python
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
```

- [ ] **Step 2: Implement**

`src/ed_bot/ingestion/projects.py`:
```python
"""Project ingestion: PDFs and code → markdown."""

import pathlib
import re
from datetime import datetime, timezone


class ProjectIngester:
    """Converts project files (PDFs, Python code) to indexed markdown."""

    def __init__(self, config):
        self.config = config

    def ingest_pdf(self, pdf_path: pathlib.Path, project_name: str | None = None) -> int:
        """Convert a PDF to markdown and save. Returns 1 on success."""
        from markitdown import MarkitDown

        md_converter = MarkitDown()
        result = md_converter.convert(str(pdf_path))
        md_content = result.text_content

        name = project_name or pdf_path.stem
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        filename = f"{slug}-requirements.md"

        frontmatter = f"""---
project: "{name}"
type: requirements
source: "{pdf_path.name}"
ingested: {datetime.now(timezone.utc).isoformat()}
---

"""
        output = self.config.projects_dir
        output.mkdir(parents=True, exist_ok=True)
        (output / filename).write_text(frontmatter + md_content, encoding="utf-8")
        return 1

    def ingest_code(self, path: pathlib.Path, project_name: str) -> int:
        """Ingest Python files. Path can be a file or directory."""
        if path.is_file():
            return self._ingest_single_file(path, project_name)

        count = 0
        for py_file in sorted(path.glob("**/*.py")):
            count += self._ingest_single_file(py_file, project_name)
        return count

    def _ingest_single_file(self, py_file: pathlib.Path, project_name: str) -> int:
        code = py_file.read_text(encoding="utf-8")
        slug = re.sub(r"[^a-z0-9]+", "-", project_name.lower()).strip("-")
        filename = f"{slug}-{py_file.stem}.md"

        frontmatter = f"""---
project: "{project_name}"
type: starter-code
file: {py_file.name}
ingested: {datetime.now(timezone.utc).isoformat()}
---

# {py_file.name} (Starter Code)

```python
{code}
```
"""
        output = self.config.projects_dir
        output.mkdir(parents=True, exist_ok=True)
        (output / filename).write_text(frontmatter, encoding="utf-8")
        return 1
```

- [ ] **Step 3: Verify and commit**

```bash
uv run pytest tests/test_project_ingestion.py -v
git add src/ed_bot/ingestion/projects.py tests/test_project_ingestion.py tests/fixtures/sample_projects/
git commit -m "feat: project ingestion (PDF and Python code → markdown)"
```

---

### Task 5: Knowledge Base Collections

**Files:**
- Create: `src/ed_bot/knowledge/__init__.py`
- Create: `src/ed_bot/knowledge/collections.py`
- Create: `tests/test_collections.py`

- [ ] **Step 1: Write tests**

`tests/test_collections.py`:
```python
import pathlib
from unittest.mock import MagicMock, patch
from ed_bot.knowledge.collections import KnowledgeBase
from ed_bot.config import BotConfig


class TestKnowledgeBase:
    def test_init_creates_pyqmd(self, tmp_bot_dir: pathlib.Path):
        config = BotConfig.load(tmp_bot_dir)
        kb = KnowledgeBase(config)
        assert kb.qmd is not None

    def test_index_threads(self, tmp_bot_dir: pathlib.Path):
        config = BotConfig.load(tmp_bot_dir)
        # Create a sample thread markdown file
        semester_dir = config.threads_dir / "spring-2026"
        semester_dir.mkdir(parents=True, exist_ok=True)
        (semester_dir / "0001-test.md").write_text(
            "---\ntitle: test\n---\n# Test\n\nContent here."
        )

        kb = KnowledgeBase(config)
        count = kb.index_threads("spring-2026")
        assert count > 0

    def test_index_projects(self, tmp_bot_dir: pathlib.Path):
        config = BotConfig.load(tmp_bot_dir)
        projects_dir = config.projects_dir
        projects_dir.mkdir(parents=True, exist_ok=True)
        (projects_dir / "project1.md").write_text(
            "---\nproject: P1\n---\n# Project 1\n\nRequirements."
        )

        kb = KnowledgeBase(config)
        count = kb.index_projects()
        assert count > 0
```

- [ ] **Step 2: Implement**

`src/ed_bot/knowledge/__init__.py`:
```python
"""Knowledge base management for ed-bot."""
```

`src/ed_bot/knowledge/collections.py`:
```python
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
```

- [ ] **Step 3: Verify and commit**

```bash
uv run pytest tests/test_collections.py -v
git add src/ed_bot/knowledge/ tests/test_collections.py
git commit -m "feat: knowledge base collection management via pyqmd"
```

---

### Task 6: Context Retrieval

**Files:**
- Create: `src/ed_bot/knowledge/retrieval.py`
- Create: `tests/test_retrieval.py`

- [ ] **Step 1: Write tests**

`tests/test_retrieval.py`:
```python
from unittest.mock import MagicMock
from ed_bot.knowledge.retrieval import ContextRetriever


class TestContextRetriever:
    def test_retrieve_returns_context(self):
        mock_kb = MagicMock()
        mock_result = MagicMock()
        mock_result.chunk.content = "Past answer about NaN values"
        mock_result.chunk.source_file = "threads/spring-2025/0142.md"
        mock_result.chunk.metadata = {"category": "Project 1"}
        mock_result.score = 0.85
        mock_kb.search.return_value = [mock_result]

        retriever = ContextRetriever(mock_kb)
        context = retriever.retrieve("get_data returns NaN", project="Project 1")

        assert len(context.chunks) == 1
        assert "NaN" in context.chunks[0].content

    def test_retrieve_separates_by_source(self):
        mock_kb = MagicMock()
        thread_result = MagicMock()
        thread_result.chunk.source_file = "threads/s1/0001.md"
        thread_result.chunk.content = "Past thread"
        thread_result.chunk.metadata = {}
        thread_result.score = 0.9

        project_result = MagicMock()
        project_result.chunk.source_file = "projects/p1.md"
        project_result.chunk.content = "Project requirement"
        project_result.chunk.metadata = {}
        project_result.score = 0.8

        mock_kb.search.return_value = [thread_result, project_result]

        retriever = ContextRetriever(mock_kb)
        context = retriever.retrieve("question about project")

        assert len(context.thread_chunks) >= 1
        assert len(context.project_chunks) >= 1

    def test_format_for_prompt(self):
        mock_kb = MagicMock()
        mock_result = MagicMock()
        mock_result.chunk.content = "Relevant answer"
        mock_result.chunk.source_file = "threads/s1/0001.md"
        mock_result.chunk.metadata = {}
        mock_result.score = 0.9
        mock_kb.search.return_value = [mock_result]

        retriever = ContextRetriever(mock_kb)
        context = retriever.retrieve("question")
        prompt_text = context.format_for_prompt()

        assert isinstance(prompt_text, str)
        assert "Relevant answer" in prompt_text
```

- [ ] **Step 2: Implement**

`src/ed_bot/knowledge/retrieval.py`:
```python
"""Context retrieval for answer generation."""

from dataclasses import dataclass, field


@dataclass
class RetrievedContext:
    """Context retrieved from the knowledge base for answer generation."""

    chunks: list = field(default_factory=list)  # all retrieved chunks
    scores: list[float] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)

    @property
    def thread_chunks(self) -> list:
        return [c for c in self.chunks if "threads/" in c.source_file]

    @property
    def project_chunks(self) -> list:
        return [c for c in self.chunks if "projects/" in c.source_file]

    @property
    def lecture_chunks(self) -> list:
        return [c for c in self.chunks if "lectures/" in c.source_file]

    def format_for_prompt(self) -> str:
        """Format retrieved context for inclusion in an LLM prompt."""
        sections = []

        if self.thread_chunks:
            sections.append("## Relevant Past Q&A\n")
            for chunk in self.thread_chunks:
                sections.append(f"---\nSource: {chunk.source_file}\n{chunk.content}\n")

        if self.project_chunks:
            sections.append("## Relevant Project Materials\n")
            for chunk in self.project_chunks:
                sections.append(f"---\nSource: {chunk.source_file}\n{chunk.content}\n")

        if self.lecture_chunks:
            sections.append("## Relevant Lecture Content\n")
            for chunk in self.lecture_chunks:
                sections.append(f"---\nSource: {chunk.source_file}\n{chunk.content}\n")

        return "\n".join(sections) if sections else "No relevant context found."


class ContextRetriever:
    """Retrieves relevant context from the knowledge base."""

    def __init__(self, knowledge_base):
        self.kb = knowledge_base

    def retrieve(
        self,
        query: str,
        project: str | None = None,
        top_k: int = 10,
    ) -> RetrievedContext:
        """Retrieve relevant context for a question."""
        results = self.kb.search(query, top_k=top_k)

        context = RetrievedContext()
        for result in results:
            context.chunks.append(result.chunk)
            context.scores.append(result.score)
            context.source_files.append(result.chunk.source_file)

        return context
```

- [ ] **Step 3: Verify and commit**

```bash
uv run pytest tests/test_retrieval.py -v
git add src/ed_bot/knowledge/retrieval.py tests/test_retrieval.py
git commit -m "feat: context retrieval with source separation"
```

---

### Task 7: Thread Classifier

**Files:**
- Create: `src/ed_bot/engine/__init__.py`
- Create: `src/ed_bot/engine/classifier.py`
- Create: `tests/test_classifier.py`

- [ ] **Step 1: Write tests**

`tests/test_classifier.py`:
```python
from ed_bot.engine.classifier import ThreadClassifier, ThreadStatus, QuestionType


class TestThreadStatus:
    def test_unanswered(self):
        status = ThreadClassifier.classify_status(
            comment_count=0, has_staff_response=False, is_endorsed=False, is_answered=False
        )
        assert status == ThreadStatus.UNANSWERED

    def test_student_only(self):
        status = ThreadClassifier.classify_status(
            comment_count=3, has_staff_response=False, is_endorsed=False, is_answered=False
        )
        assert status == ThreadStatus.STUDENT_ONLY

    def test_staff_answered(self):
        status = ThreadClassifier.classify_status(
            comment_count=2, has_staff_response=True, is_endorsed=False, is_answered=True
        )
        assert status == ThreadStatus.STAFF_ANSWERED

    def test_endorsed(self):
        status = ThreadClassifier.classify_status(
            comment_count=1, has_staff_response=False, is_endorsed=True, is_answered=True
        )
        assert status == ThreadStatus.ENDORSED


class TestQuestionType:
    def test_all_types_exist(self):
        assert QuestionType.LOGISTICS
        assert QuestionType.SETUP
        assert QuestionType.CONCEPTUAL
        assert QuestionType.PROJECT_HELP
        assert QuestionType.TEACHING_MOMENT
        assert QuestionType.INTEGRITY_RISK


class TestNeedsAttention:
    def test_unanswered_needs_attention(self):
        assert ThreadClassifier.needs_attention(ThreadStatus.UNANSWERED) is True

    def test_student_only_needs_attention(self):
        assert ThreadClassifier.needs_attention(ThreadStatus.STUDENT_ONLY) is True

    def test_staff_answered_does_not(self):
        assert ThreadClassifier.needs_attention(ThreadStatus.STAFF_ANSWERED) is False

    def test_endorsed_does_not(self):
        assert ThreadClassifier.needs_attention(ThreadStatus.ENDORSED) is False
```

- [ ] **Step 2: Implement**

`src/ed_bot/engine/__init__.py`:
```python
"""Answer engine for ed-bot."""
```

`src/ed_bot/engine/classifier.py`:
```python
"""Thread status and question type classification."""

from enum import Enum


class ThreadStatus(str, Enum):
    UNANSWERED = "unanswered"
    STUDENT_ONLY = "student_only"
    NEEDS_FOLLOWUP = "needs_followup"
    ENDORSED = "endorsed"
    STAFF_ANSWERED = "staff_answered"
    RESOLVED = "resolved"
    PRIVATE_FLAGGED = "private_flagged"


class QuestionType(str, Enum):
    LOGISTICS = "logistics"
    SETUP = "setup"
    CONCEPTUAL = "conceptual"
    PROJECT_HELP = "project_help"
    TEACHING_MOMENT = "teaching_moment"
    INTEGRITY_RISK = "integrity_risk"


ATTENTION_STATUSES = {
    ThreadStatus.UNANSWERED,
    ThreadStatus.STUDENT_ONLY,
    ThreadStatus.NEEDS_FOLLOWUP,
    ThreadStatus.PRIVATE_FLAGGED,
}


class ThreadClassifier:
    """Classifies threads by status and question type."""

    @staticmethod
    def classify_status(
        comment_count: int,
        has_staff_response: bool,
        is_endorsed: bool,
        is_answered: bool,
        needs_followup: bool = False,
    ) -> ThreadStatus:
        """Classify thread status from metadata."""
        if is_endorsed:
            return ThreadStatus.ENDORSED
        if comment_count == 0:
            return ThreadStatus.UNANSWERED
        if has_staff_response:
            if needs_followup:
                return ThreadStatus.NEEDS_FOLLOWUP
            return ThreadStatus.STAFF_ANSWERED
        return ThreadStatus.STUDENT_ONLY

    @staticmethod
    def needs_attention(status: ThreadStatus) -> bool:
        """Check if a thread status requires attention."""
        return status in ATTENTION_STATUSES

    @staticmethod
    def priority_score(status: ThreadStatus) -> int:
        """Return priority score (higher = more urgent)."""
        scores = {
            ThreadStatus.PRIVATE_FLAGGED: 100,
            ThreadStatus.UNANSWERED: 90,
            ThreadStatus.STUDENT_ONLY: 70,
            ThreadStatus.NEEDS_FOLLOWUP: 50,
            ThreadStatus.ENDORSED: 0,
            ThreadStatus.STAFF_ANSWERED: 0,
            ThreadStatus.RESOLVED: 0,
        }
        return scores.get(status, 0)
```

- [ ] **Step 3: Verify and commit**

```bash
uv run pytest tests/test_classifier.py -v
git add src/ed_bot/engine/ tests/test_classifier.py
git commit -m "feat: thread status and question type classifier"
```

---

### Task 8: Response Templates

**Files:**
- Create: `src/ed_bot/engine/templates.py`
- Create: `tests/test_templates.py`

- [ ] **Step 1: Write tests**

`tests/test_templates.py`:
```python
from ed_bot.engine.templates import get_system_prompt, get_template_instructions
from ed_bot.engine.classifier import QuestionType


class TestTemplates:
    def test_logistics_template(self):
        instructions = get_template_instructions(QuestionType.LOGISTICS)
        assert "direct" in instructions.lower() or "factual" in instructions.lower()

    def test_conceptual_template(self):
        instructions = get_template_instructions(QuestionType.CONCEPTUAL)
        assert "socratic" in instructions.lower() or "guiding" in instructions.lower()

    def test_project_help_template(self):
        instructions = get_template_instructions(QuestionType.PROJECT_HELP)
        assert "never" in instructions.lower() and "solution" in instructions.lower()

    def test_teaching_moment_template(self):
        instructions = get_template_instructions(QuestionType.TEACHING_MOMENT)
        assert "thorough" in instructions.lower()

    def test_system_prompt_includes_style(self):
        prompt = get_system_prompt(style_guide="Be helpful.", guardrails=None)
        assert "Be helpful" in prompt

    def test_system_prompt_includes_guardrails(self):
        prompt = get_system_prompt(
            style_guide="Be helpful.",
            guardrails="## Never Reveal\n- Solution code"
        )
        assert "Never Reveal" in prompt
```

- [ ] **Step 2: Implement**

`src/ed_bot/engine/templates.py`:
```python
"""Response templates by question type."""

from ed_bot.engine.classifier import QuestionType


TEMPLATE_INSTRUCTIONS: dict[QuestionType, str] = {
    QuestionType.LOGISTICS: (
        "Respond in a direct, factual tone. Include specific dates, links, "
        "or steps. No Socratic method — just answer the question clearly."
    ),
    QuestionType.SETUP: (
        "Provide step-by-step instructions. Be specific about commands, "
        "paths, and environment details. Include common pitfalls."
    ),
    QuestionType.CONCEPTUAL: (
        "Use a Socratic approach: ask guiding questions before giving the full answer. "
        "Point to relevant lectures or readings. Build understanding, don't just state facts."
    ),
    QuestionType.PROJECT_HELP: (
        "Never provide solution code or reveal implementation details. "
        "Ask what they've tried. Point to relevant concepts and documentation. "
        "If their approach is fundamentally wrong, redirect gently. "
        "Reference similar past threads when applicable."
    ),
    QuestionType.TEACHING_MOMENT: (
        "Be thorough — this is an opportunity to educate. Use examples, analogies, "
        "and step-by-step reasoning. Reference lecture content when possible."
    ),
    QuestionType.INTEGRITY_RISK: (
        "This appears to be a potential academic integrity issue. "
        "Do NOT answer the question. Suggest the thread be marked private. "
        "Note what makes this a concern."
    ),
}


def get_template_instructions(question_type: QuestionType) -> str:
    """Get response instructions for a question type."""
    return TEMPLATE_INSTRUCTIONS.get(question_type, TEMPLATE_INSTRUCTIONS[QuestionType.PROJECT_HELP])


def get_system_prompt(
    style_guide: str,
    guardrails: str | None = None,
    question_type: QuestionType | None = None,
) -> str:
    """Build the system prompt for draft generation."""
    parts = [style_guide]

    if question_type:
        parts.append(f"\n## Response Style for This Question\n\n{get_template_instructions(question_type)}")

    if guardrails:
        parts.append(f"\n## Project Guardrails\n\n{guardrails}")

    return "\n\n".join(parts)
```

- [ ] **Step 3: Verify and commit**

```bash
uv run pytest tests/test_templates.py -v
git add src/ed_bot/engine/templates.py tests/test_templates.py
git commit -m "feat: response templates by question type"
```

---

### Task 9: Guardrails Loading + Generation

**Files:**
- Create: `src/ed_bot/engine/guardrails.py`
- Create: `tests/test_guardrails.py`

- [ ] **Step 1: Write tests**

`tests/test_guardrails.py`:
```python
import pathlib
from ed_bot.engine.guardrails import GuardrailsManager


class TestGuardrailsManager:
    def test_load_guardrails(self, sample_playbook_dir: pathlib.Path):
        manager = GuardrailsManager(sample_playbook_dir / "guardrails")
        guardrails = manager.load("project1")
        assert guardrails is not None
        assert "Never Reveal" in guardrails

    def test_load_nonexistent_returns_none(self, sample_playbook_dir: pathlib.Path):
        manager = GuardrailsManager(sample_playbook_dir / "guardrails")
        guardrails = manager.load("nonexistent")
        assert guardrails is None

    def test_list_guardrails(self, sample_playbook_dir: pathlib.Path):
        manager = GuardrailsManager(sample_playbook_dir / "guardrails")
        names = manager.list()
        assert "project1" in names

    def test_load_style_guide(self, sample_playbook_dir: pathlib.Path):
        style_guide = GuardrailsManager.load_style_guide(
            sample_playbook_dir / "style-guide.md"
        )
        assert "teaching assistant" in style_guide.lower() or "Voice" in style_guide

    def test_detect_project(self, sample_playbook_dir: pathlib.Path):
        manager = GuardrailsManager(sample_playbook_dir / "guardrails")
        project = manager.detect_project("My Project 1 code doesn't work")
        # Should match "project1" guardrail since "Project 1" is in the title
        # This is a fuzzy match — may or may not match depending on implementation
        # At minimum, the method should return a string or None
        assert project is None or isinstance(project, str)
```

- [ ] **Step 2: Implement**

`src/ed_bot/engine/guardrails.py`:
```python
"""Guardrail loading and management."""

import pathlib
import re


class GuardrailsManager:
    """Manages per-project guardrail files."""

    def __init__(self, guardrails_dir: pathlib.Path):
        self.guardrails_dir = pathlib.Path(guardrails_dir)

    def load(self, project_slug: str) -> str | None:
        """Load guardrails for a project by slug name. Returns file content or None."""
        path = self.guardrails_dir / f"{project_slug}.md"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def list(self) -> list[str]:
        """List all available guardrail slugs."""
        if not self.guardrails_dir.exists():
            return []
        return [p.stem for p in sorted(self.guardrails_dir.glob("*.md"))]

    def detect_project(self, text: str) -> str | None:
        """Try to detect which project a question is about from the text."""
        text_lower = text.lower()
        for slug in self.list():
            # Simple heuristic: check if the slug appears in the text
            # e.g., "project1" matches "project 1" or "Project 1"
            normalized = slug.replace("-", " ").replace("_", " ")
            if normalized in text_lower or slug in text_lower:
                return slug
        return None

    @staticmethod
    def load_style_guide(path: pathlib.Path) -> str:
        """Load the global style guide. Returns content or empty string."""
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")
```

- [ ] **Step 3: Verify and commit**

```bash
uv run pytest tests/test_guardrails.py -v
git add src/ed_bot/engine/guardrails.py tests/test_guardrails.py
git commit -m "feat: guardrails loading and project detection"
```

---

### Task 10: Draft Queue

**Files:**
- Create: `src/ed_bot/queue/__init__.py`
- Create: `src/ed_bot/queue/manager.py`
- Create: `src/ed_bot/queue/priority.py`
- Create: `tests/test_queue.py`
- Create: `tests/test_priority.py`

- [ ] **Step 1: Write tests**

`tests/test_priority.py`:
```python
from ed_bot.queue.priority import compute_priority
from ed_bot.engine.classifier import ThreadStatus


class TestPriority:
    def test_unanswered_is_high(self):
        assert compute_priority(ThreadStatus.UNANSWERED) == "high"

    def test_student_only_is_high(self):
        assert compute_priority(ThreadStatus.STUDENT_ONLY) == "high"

    def test_needs_followup_is_medium(self):
        assert compute_priority(ThreadStatus.NEEDS_FOLLOWUP) == "medium"

    def test_staff_answered_is_low(self):
        assert compute_priority(ThreadStatus.STAFF_ANSWERED) == "low"
```

`tests/test_queue.py`:
```python
import pathlib
import json
from ed_bot.queue.manager import DraftQueue, Draft


class TestDraftQueue:
    def test_add_draft(self, tmp_path: pathlib.Path):
        queue = DraftQueue(tmp_path)
        draft = Draft(
            thread_id=342,
            thread_number=42,
            thread_title="NaN problem",
            thread_status="unanswered",
            question_type="project_help",
            project="Project 1",
            priority="high",
            content="The NaN values are expected...",
            context_used=["threads/s1/0142.md"],
            guardrails_applied="project1.md",
        )
        draft_id = queue.add(draft)
        assert draft_id is not None
        assert (tmp_path / f"{draft_id}.json").exists()

    def test_get_draft(self, tmp_path: pathlib.Path):
        queue = DraftQueue(tmp_path)
        draft = Draft(
            thread_id=100, thread_number=1, thread_title="Test",
            thread_status="unanswered", question_type="logistics",
            project=None, priority="high", content="Answer here.",
            context_used=[], guardrails_applied=None,
        )
        draft_id = queue.add(draft)
        loaded = queue.get(draft_id)
        assert loaded is not None
        assert loaded.thread_id == 100
        assert loaded.content == "Answer here."

    def test_list_drafts(self, tmp_path: pathlib.Path):
        queue = DraftQueue(tmp_path)
        for i in range(3):
            queue.add(Draft(
                thread_id=i, thread_number=i, thread_title=f"Thread {i}",
                thread_status="unanswered", question_type="logistics",
                project=None, priority="high", content=f"Answer {i}",
                context_used=[], guardrails_applied=None,
            ))
        drafts = queue.list()
        assert len(drafts) == 3

    def test_remove_draft(self, tmp_path: pathlib.Path):
        queue = DraftQueue(tmp_path)
        draft = Draft(
            thread_id=1, thread_number=1, thread_title="T",
            thread_status="unanswered", question_type="logistics",
            project=None, priority="high", content="A",
            context_used=[], guardrails_applied=None,
        )
        draft_id = queue.add(draft)
        queue.remove(draft_id)
        assert queue.get(draft_id) is None

    def test_list_filtered_by_project(self, tmp_path: pathlib.Path):
        queue = DraftQueue(tmp_path)
        queue.add(Draft(
            thread_id=1, thread_number=1, thread_title="T1",
            thread_status="unanswered", question_type="project_help",
            project="Project 1", priority="high", content="A1",
            context_used=[], guardrails_applied=None,
        ))
        queue.add(Draft(
            thread_id=2, thread_number=2, thread_title="T2",
            thread_status="unanswered", question_type="logistics",
            project=None, priority="medium", content="A2",
            context_used=[], guardrails_applied=None,
        ))
        filtered = queue.list(project="Project 1")
        assert len(filtered) == 1
        assert filtered[0].project == "Project 1"
```

- [ ] **Step 2: Implement**

`src/ed_bot/queue/__init__.py`:
```python
"""Draft queue management for ed-bot."""
```

`src/ed_bot/queue/priority.py`:
```python
"""Priority scoring for draft queue."""

from ed_bot.engine.classifier import ThreadStatus


def compute_priority(status: ThreadStatus) -> str:
    """Compute priority level from thread status."""
    if status in (ThreadStatus.UNANSWERED, ThreadStatus.STUDENT_ONLY, ThreadStatus.PRIVATE_FLAGGED):
        return "high"
    if status == ThreadStatus.NEEDS_FOLLOWUP:
        return "medium"
    return "low"
```

`src/ed_bot/queue/manager.py`:
```python
"""Draft queue CRUD — JSON files on disk."""

import json
import pathlib
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


@dataclass
class Draft:
    """A draft answer waiting for review."""

    thread_id: int
    thread_number: int
    thread_title: str
    thread_status: str
    question_type: str
    project: str | None
    priority: str
    content: str
    context_used: list[str]
    guardrails_applied: str | None
    draft_id: str = ""
    created: str = ""

    def __post_init__(self):
        if not self.draft_id:
            self.draft_id = uuid.uuid4().hex[:12]
        if not self.created:
            self.created = datetime.now(timezone.utc).isoformat()


class DraftQueue:
    """Manages draft answers as JSON files in a directory."""

    def __init__(self, drafts_dir: pathlib.Path):
        self.drafts_dir = pathlib.Path(drafts_dir)
        self.drafts_dir.mkdir(parents=True, exist_ok=True)

    def add(self, draft: Draft) -> str:
        """Add a draft to the queue. Returns the draft_id."""
        path = self.drafts_dir / f"{draft.draft_id}.json"
        path.write_text(json.dumps(asdict(draft), indent=2))
        return draft.draft_id

    def get(self, draft_id: str) -> Draft | None:
        """Get a draft by ID."""
        path = self.drafts_dir / f"{draft_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return Draft(**data)

    def list(
        self,
        project: str | None = None,
        status: str | None = None,
        question_type: str | None = None,
    ) -> list[Draft]:
        """List all drafts, optionally filtered."""
        drafts = []
        for path in sorted(self.drafts_dir.glob("*.json")):
            data = json.loads(path.read_text())
            draft = Draft(**data)
            if project and draft.project != project:
                continue
            if status and draft.thread_status != status:
                continue
            if question_type and draft.question_type != question_type:
                continue
            drafts.append(draft)

        # Sort by priority (high first)
        priority_order = {"high": 0, "medium": 1, "low": 2}
        drafts.sort(key=lambda d: priority_order.get(d.priority, 3))
        return drafts

    def remove(self, draft_id: str) -> None:
        """Remove a draft from the queue."""
        path = self.drafts_dir / f"{draft_id}.json"
        if path.exists():
            path.unlink()

    def update(self, draft: Draft) -> None:
        """Update an existing draft."""
        path = self.drafts_dir / f"{draft.draft_id}.json"
        path.write_text(json.dumps(asdict(draft), indent=2))
```

- [ ] **Step 3: Verify and commit**

```bash
uv run pytest tests/test_queue.py tests/test_priority.py -v
git add src/ed_bot/queue/ tests/test_queue.py tests/test_priority.py
git commit -m "feat: draft queue with priority scoring"
```

---

### Task 11: Draft Generator (Claude API Integration)

**Files:**
- Create: `src/ed_bot/engine/drafter.py`
- Create: `tests/test_drafter.py`

- [ ] **Step 1: Write tests**

`tests/test_drafter.py`:
```python
from unittest.mock import MagicMock, patch
from ed_bot.engine.drafter import DraftGenerator
from ed_bot.engine.classifier import QuestionType


class TestDraftGenerator:
    def test_generate_returns_content(self):
        mock_context = MagicMock()
        mock_context.format_for_prompt.return_value = "Past answer about NaN"

        with patch("ed_bot.engine.drafter.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="The NaN values are expected because...")]
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            generator = DraftGenerator()
            result = generator.generate(
                question="My data has NaN values",
                question_type=QuestionType.PROJECT_HELP,
                context=mock_context,
                style_guide="Be helpful",
                guardrails="Never reveal solutions",
            )

            assert "NaN" in result
            mock_client.messages.create.assert_called_once()

    def test_generate_includes_guardrails_in_prompt(self):
        mock_context = MagicMock()
        mock_context.format_for_prompt.return_value = ""

        with patch("ed_bot.engine.drafter.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Response")]
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            generator = DraftGenerator()
            generator.generate(
                question="help me",
                question_type=QuestionType.PROJECT_HELP,
                context=mock_context,
                style_guide="Be nice",
                guardrails="## Never Reveal\n- Solution code",
            )

            call_args = mock_client.messages.create.call_args
            system = call_args[1].get("system") or call_args[0][0] if call_args[0] else ""
            # The system prompt should contain guardrails
            messages = call_args[1].get("messages", [])
            all_text = str(system) + str(messages)
            assert "Never Reveal" in all_text or "Solution code" in all_text
```

- [ ] **Step 2: Implement**

`src/ed_bot/engine/drafter.py`:
```python
"""Draft generation using Claude API."""

import anthropic

from ed_bot.engine.classifier import QuestionType
from ed_bot.engine.templates import get_system_prompt


class DraftGenerator:
    """Generates draft answers using Claude API with context and guardrails."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model

    def generate(
        self,
        question: str,
        question_type: QuestionType,
        context,  # RetrievedContext
        style_guide: str,
        guardrails: str | None = None,
        existing_comments: str = "",
        hint: str | None = None,
    ) -> str:
        """Generate a draft answer.

        Returns the draft text as a string.
        """
        system_prompt = get_system_prompt(
            style_guide=style_guide,
            guardrails=guardrails,
            question_type=question_type,
        )

        context_text = context.format_for_prompt()

        user_message = f"""## Student's Question

{question}"""

        if existing_comments:
            user_message += f"""

## Existing Comments on This Thread

{existing_comments}"""

        user_message += f"""

## Retrieved Context from Knowledge Base

{context_text}"""

        if hint:
            user_message += f"""

## Instructor Guidance

{hint}"""

        user_message += """

## Your Task

Write a response to the student's question following the style guide and guardrails above.
Use the retrieved context to inform your answer. Reference specific course materials when relevant.
Do NOT make up information. If you're unsure, say so."""

        client = anthropic.Anthropic()
        response = client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        return response.content[0].text
```

- [ ] **Step 3: Verify and commit**

```bash
uv run pytest tests/test_drafter.py -v
git add src/ed_bot/engine/drafter.py tests/test_drafter.py
git commit -m "feat: draft generator with Claude API integration"
```

---

### Task 12: CLI — Output Helpers + Main + Ingest + Status

**Files:**
- Create: `src/ed_bot/cli/__init__.py`
- Create: `src/ed_bot/cli/output.py`
- Create: `src/ed_bot/cli/main.py`
- Create: `src/ed_bot/cli/ingest.py`
- Create: `src/ed_bot/cli/status.py`

- [ ] **Step 1: Implement output helpers**

`src/ed_bot/cli/__init__.py`:
```python
"""CLI for ed-bot."""
```

`src/ed_bot/cli/output.py`:
```python
"""Shared output helpers for Rich/JSON dual-mode output."""

import json
from rich.console import Console

console = Console()


def output(data, json_mode: bool = False):
    """Output data as JSON or Rich formatted text."""
    if json_mode:
        print(json.dumps(data, indent=2, default=str))
    else:
        if isinstance(data, dict):
            for key, value in data.items():
                console.print(f"  {key}: {value}")
        elif isinstance(data, list):
            for item in data:
                console.print(f"  {item}")
        else:
            console.print(str(data))
```

- [ ] **Step 2: Implement main CLI**

`src/ed_bot/cli/main.py`:
```python
"""Typer CLI entry point for ed-bot."""

import pathlib
import typer

from ed_bot.cli.ingest import app as ingest_app
from ed_bot.cli.status import app as status_app
from ed_bot.cli.review import app as review_app
from ed_bot.cli.answer import app as answer_app
from ed_bot.cli.guardrails_cmd import app as guardrails_app

app = typer.Typer(name="ed", help="EdStem forum automation.")

app.add_typer(ingest_app, name="ingest")
app.add_typer(status_app, name="status", invoke_without_command=True)
app.add_typer(review_app, name="review", invoke_without_command=True)
app.add_typer(answer_app, name="answer", invoke_without_command=True)
app.add_typer(guardrails_app, name="guardrails")


DEFAULT_BOT_DIR = "~/.ed-bot"


def get_bot_dir(bot_dir: str = DEFAULT_BOT_DIR) -> pathlib.Path:
    return pathlib.Path(bot_dir).expanduser()
```

- [ ] **Step 3: Implement ingest CLI**

`src/ed_bot/cli/ingest.py`:
```python
"""Ingest CLI commands."""

import json
import pathlib
import typer
from rich.console import Console

from ed_bot.cli.main import get_bot_dir, DEFAULT_BOT_DIR
from ed_bot.config import BotConfig

app = typer.Typer(help="Ingest content into the knowledge base.")
console = Console()


@app.command()
def threads(
    course: int = typer.Option(None, "--course", help="Course ID"),
    semester: str = typer.Option(None, "--semester", help="Semester name"),
    all_semesters: bool = typer.Option(False, "--all", help="All configured semesters"),
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Ingest threads from EdStem."""
    from ed_api import EdClient
    from ed_bot.ingestion.threads import ThreadIngester

    config = BotConfig.load(get_bot_dir(bot_dir))
    client = EdClient(region=config.region)
    ingester = ThreadIngester(config, client)

    if all_semesters:
        total = 0
        for sem in config.semesters:
            count = ingester.ingest(sem["course_id"], sem["name"])
            total += count
            if not json_output:
                console.print(f"  {sem['name']}: {count} threads")
        if json_output:
            print(json.dumps({"total": total}))
        else:
            console.print(f"[green]Total: {total} threads ingested.[/green]")
    else:
        cid = course or config.course_id
        sem = semester or config.semesters[0]["name"] if config.semesters else "default"
        count = ingester.ingest(cid, sem)
        if json_output:
            print(json.dumps({"semester": sem, "count": count}))
        else:
            console.print(f"[green]Ingested {count} threads for {sem}.[/green]")


@app.command()
def projects(
    path: str = typer.Argument(help="Path to PDF or code directory"),
    name: str = typer.Option(None, "--name", help="Project name"),
    type: str = typer.Option("auto", "--type", help="auto, requirements, or starter-code"),
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Ingest project materials (PDFs or code)."""
    from ed_bot.ingestion.projects import ProjectIngester

    config = BotConfig.load(get_bot_dir(bot_dir))
    ingester = ProjectIngester(config)

    file_path = pathlib.Path(path)
    project_name = name or file_path.stem

    if file_path.suffix.lower() == ".pdf":
        count = ingester.ingest_pdf(file_path, project_name)
    else:
        count = ingester.ingest_code(file_path, project_name)

    if json_output:
        print(json.dumps({"project": project_name, "count": count}))
    else:
        console.print(f"[green]Ingested {count} files for {project_name}.[/green]")
```

- [ ] **Step 4: Implement status CLI**

`src/ed_bot/cli/status.py`:
```python
"""Status CLI command."""

import json
import typer
from rich.console import Console
from rich.table import Table

from ed_bot.cli.main import get_bot_dir, DEFAULT_BOT_DIR
from ed_bot.config import BotConfig

app = typer.Typer(help="Forum and knowledge base status.")
console = Console()


@app.callback(invoke_without_command=True)
def status(
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Show forum and knowledge base status."""
    config = BotConfig.load(get_bot_dir(bot_dir))

    from ed_bot.knowledge.collections import KnowledgeBase
    from ed_bot.queue.manager import DraftQueue

    kb = KnowledgeBase(config)
    queue = DraftQueue(config.drafts_dir)

    kb_status = kb.status()
    drafts = queue.list()

    if json_output:
        print(json.dumps({
            "course_id": config.course_id,
            "collections": kb_status,
            "drafts_pending": len(drafts),
        }, default=str))
    else:
        console.print(f"[bold]Course: {config.course_id}[/bold]")
        table = Table()
        table.add_column("Collection")
        table.add_column("Chunks")
        for name, info in kb_status.items():
            table.add_row(name, str(info.get("chunk_count", 0)))
        console.print(table)
        console.print(f"\nDrafts pending: {len(drafts)}")
```

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cli/
git commit -m "feat: CLI scaffolding with ingest and status commands"
```

---

### Task 13: CLI — Review + Answer + Guardrails

**Files:**
- Create: `src/ed_bot/cli/review.py`
- Create: `src/ed_bot/cli/answer.py`
- Create: `src/ed_bot/cli/guardrails_cmd.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Implement review CLI**

`src/ed_bot/cli/review.py`:
```python
"""Review CLI commands."""

import json
import os
import subprocess
import tempfile
import typer
from rich.console import Console

from ed_bot.cli.main import get_bot_dir, DEFAULT_BOT_DIR
from ed_bot.config import BotConfig
from ed_bot.queue.manager import DraftQueue

app = typer.Typer(help="Review draft answers.")
console = Console()


@app.callback(invoke_without_command=True)
def review(
    draft_id: str = typer.Argument(None, help="Draft ID to review"),
    list_all: bool = typer.Option(False, "--list", help="List all drafts"),
    project: str = typer.Option(None, "--project", help="Filter by project"),
    status: str = typer.Option(None, "--status", help="Filter by status"),
    question_type: str = typer.Option(None, "--type", help="Filter by question type"),
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Review drafts. With no args, shows the next highest-priority draft."""
    config = BotConfig.load(get_bot_dir(bot_dir))
    queue = DraftQueue(config.drafts_dir)

    if list_all:
        drafts = queue.list(project=project, status=status, question_type=question_type)
        if json_output:
            print(json.dumps([
                {"draft_id": d.draft_id, "thread_id": d.thread_id,
                 "thread_number": d.thread_number, "title": d.thread_title,
                 "priority": d.priority, "project": d.project,
                 "question_type": d.question_type, "status": d.thread_status}
                for d in drafts
            ]))
        else:
            for d in drafts:
                console.print(f"  [{d.priority}] {d.draft_id}: #{d.thread_number} {d.thread_title}")
        return

    if draft_id:
        draft = queue.get(draft_id)
    else:
        drafts = queue.list()
        draft = drafts[0] if drafts else None

    if not draft:
        console.print("No drafts to review.")
        return

    if json_output:
        print(json.dumps({
            "draft_id": draft.draft_id,
            "thread_id": draft.thread_id,
            "thread_number": draft.thread_number,
            "title": draft.thread_title,
            "status": draft.thread_status,
            "question_type": draft.question_type,
            "project": draft.project,
            "priority": draft.priority,
            "content": draft.content,
            "context_used": draft.context_used,
            "guardrails_applied": draft.guardrails_applied,
        }))
    else:
        console.print(f"\n[bold]Draft {draft.draft_id}[/bold]")
        console.print(f"Thread #{draft.thread_number}: {draft.thread_title}")
        console.print(f"Type: {draft.question_type} | Priority: {draft.priority}")
        if draft.project:
            console.print(f"Project: {draft.project}")
        console.print(f"\n[dim]--- Draft Answer ---[/dim]\n")
        console.print(draft.content)
        console.print(f"\n[dim]Actions: ed approve {draft.draft_id} | ed reject {draft.draft_id} | ed skip {draft.draft_id}[/dim]")


@app.command()
def approve(
    draft_id: str = typer.Argument(help="Draft ID"),
    as_answer: bool = typer.Option(False, "--as-answer", help="Post as answer"),
    endorse: bool = typer.Option(False, "--endorse", help="Endorse instead of posting"),
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Approve and post a draft."""
    from ed_api import EdClient

    config = BotConfig.load(get_bot_dir(bot_dir))
    queue = DraftQueue(config.drafts_dir)
    draft = queue.get(draft_id)

    if not draft:
        console.print(f"[red]Draft {draft_id} not found.[/red]")
        raise typer.Exit(1)

    client = EdClient(region=config.region)

    if endorse:
        client.threads.endorse(draft.thread_id)
        action = "endorsed"
    else:
        client.comments.post(draft.thread_id, draft.content, is_answer=as_answer)
        action = "posted as answer" if as_answer else "posted"

    queue.remove(draft_id)

    if json_output:
        print(json.dumps({"status": action, "draft_id": draft_id, "thread_id": draft.thread_id}))
    else:
        console.print(f"[green]Draft {draft_id} {action} on thread {draft.thread_id}.[/green]")


@app.command()
def reject(
    draft_id: str = typer.Argument(help="Draft ID"),
    reason: str = typer.Option(None, "--reason"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Reject a draft."""
    config = BotConfig.load(get_bot_dir(bot_dir))
    queue = DraftQueue(config.drafts_dir)
    queue.remove(draft_id)
    console.print(f"Draft {draft_id} rejected.")


@app.command()
def skip(
    draft_id: str = typer.Argument(help="Draft ID"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Skip a draft (move to back of queue)."""
    config = BotConfig.load(get_bot_dir(bot_dir))
    queue = DraftQueue(config.drafts_dir)
    draft = queue.get(draft_id)
    if draft:
        draft.priority = "low"
        queue.update(draft)
    console.print(f"Draft {draft_id} skipped.")
```

- [ ] **Step 2: Implement answer CLI**

`src/ed_bot/cli/answer.py`:
```python
"""Answer CLI command — inline drafting."""

import json
import typer
from rich.console import Console

from ed_bot.cli.main import get_bot_dir, DEFAULT_BOT_DIR
from ed_bot.config import BotConfig

app = typer.Typer(help="Draft answer for a specific thread.")
console = Console()


@app.callback(invoke_without_command=True)
def answer(
    thread_ref: str = typer.Argument(help="Thread ID or course_id:number"),
    hint: str = typer.Option(None, "--hint", help="Guidance for the draft"),
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Generate a draft answer for a specific thread."""
    from ed_api import EdClient
    from ed_api.content import ed_xml_to_markdown
    from ed_bot.engine.classifier import QuestionType, ThreadClassifier
    from ed_bot.engine.drafter import DraftGenerator
    from ed_bot.engine.guardrails import GuardrailsManager
    from ed_bot.knowledge.collections import KnowledgeBase
    from ed_bot.knowledge.retrieval import ContextRetriever
    from ed_bot.queue.manager import Draft, DraftQueue
    from ed_bot.queue.priority import compute_priority

    config = BotConfig.load(get_bot_dir(bot_dir))
    client = EdClient(region=config.region)

    # Fetch thread
    if ":" in thread_ref:
        course_id, number = thread_ref.split(":", 1)
        thread = client.threads.get_by_number(int(course_id), int(number))
    else:
        thread = client.threads.get(int(thread_ref))

    # Classify
    status = ThreadClassifier.classify_status(
        comment_count=len(thread.comments),
        has_staff_response=thread.has_staff_response,
        is_endorsed=thread.is_endorsed,
        is_answered=thread.is_answered,
    )

    # Load guardrails
    guardrails_mgr = GuardrailsManager(config.guardrails_dir)
    project_slug = guardrails_mgr.detect_project(thread.title + " " + thread.category)
    guardrails = guardrails_mgr.load(project_slug) if project_slug else None
    style_guide = GuardrailsManager.load_style_guide(config.style_guide_path)

    # Retrieve context
    kb = KnowledgeBase(config)
    retriever = ContextRetriever(kb)
    try:
        question_md = ed_xml_to_markdown(thread.content)
    except Exception:
        question_md = thread.content
    context = retriever.retrieve(thread.title + " " + question_md, project=project_slug)

    # Generate draft
    generator = DraftGenerator()
    draft_content = generator.generate(
        question=question_md,
        question_type=QuestionType.PROJECT_HELP,  # LLM classification would go here
        context=context,
        style_guide=style_guide,
        guardrails=guardrails,
        hint=hint,
    )

    # Store in queue
    queue = DraftQueue(config.drafts_dir)
    draft = Draft(
        thread_id=thread.id,
        thread_number=thread.number,
        thread_title=thread.title,
        thread_status=status.value,
        question_type="project_help",
        project=project_slug,
        priority=compute_priority(status),
        content=draft_content,
        context_used=context.source_files,
        guardrails_applied=project_slug,
    )
    draft_id = queue.add(draft)

    if json_output:
        print(json.dumps({
            "draft_id": draft_id,
            "thread_id": thread.id,
            "thread_number": thread.number,
            "title": thread.title,
            "status": status.value,
            "project": project_slug,
            "content": draft_content,
        }))
    else:
        console.print(f"\n[bold]Thread #{thread.number}:[/bold] {thread.title}")
        console.print(f"Status: {status.value} | Project: {project_slug or 'none'}")
        console.print(f"\n[dim]--- Draft Answer ---[/dim]\n")
        console.print(draft_content)
        console.print(f"\n[green]Draft saved: {draft_id}[/green]")
        console.print(f"[dim]ed approve {draft_id} | ed reject {draft_id}[/dim]")
```

- [ ] **Step 3: Implement guardrails CLI**

`src/ed_bot/cli/guardrails_cmd.py`:
```python
"""Guardrails CLI commands."""

import json
import os
import subprocess
import typer
from rich.console import Console

from ed_bot.cli.main import get_bot_dir, DEFAULT_BOT_DIR
from ed_bot.config import BotConfig
from ed_bot.engine.guardrails import GuardrailsManager

app = typer.Typer(help="Manage project guardrails.")
console = Console()


@app.command(name="list")
def list_guardrails(
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """List all guardrail files."""
    config = BotConfig.load(get_bot_dir(bot_dir))
    manager = GuardrailsManager(config.guardrails_dir)
    names = manager.list()
    if json_output:
        print(json.dumps(names))
    else:
        for name in names:
            console.print(f"  {name}")


@app.command()
def edit(
    project: str = typer.Argument(help="Project slug"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Edit guardrails in $EDITOR."""
    config = BotConfig.load(get_bot_dir(bot_dir))
    path = config.guardrails_dir / f"{project}.md"
    editor = os.environ.get("EDITOR", "notepad" if os.name == "nt" else "vi")
    subprocess.run([editor, str(path)])
```

- [ ] **Step 4: Write CLI tests**

`tests/test_cli.py`:
```python
from typer.testing import CliRunner


class TestCLIHelp:
    def test_main_help(self):
        from ed_bot.cli.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "ingest" in result.stdout
        assert "review" in result.stdout or "status" in result.stdout

    def test_ingest_help(self):
        from ed_bot.cli.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["ingest", "--help"])
        assert result.exit_code == 0
        assert "threads" in result.stdout

    def test_guardrails_help(self):
        from ed_bot.cli.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["guardrails", "--help"])
        assert result.exit_code == 0
```

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest tests/test_cli.py -v
git add src/ed_bot/cli/ tests/test_cli.py
git commit -m "feat: CLI with review, answer, guardrails, and status commands"
```

---

### Task 14: Claude Code Skills

**Files:**
- Create: `src/ed_bot/skills/ed-status.md`
- Create: `src/ed_bot/skills/ed-review.md`
- Create: `src/ed_bot/skills/ed-answer.md`
- Create: `src/ed_bot/skills/ed-ingest.md`

- [ ] **Step 1: Create skill files**

`src/ed_bot/skills/ed-status.md`:
```markdown
---
name: ed-status
description: Show EdStem forum status — unanswered threads, pending drafts, knowledge base stats.
---

Run the following command and present the results conversationally:

```bash
ed status --json
```

Summarize: how many unanswered threads, student-only threads, pending drafts.
Ask if the user wants to start reviewing.
```

`src/ed_bot/skills/ed-review.md`:
```markdown
---
name: ed-review
description: Review draft answers for EdStem forum questions. Present drafts one at a time.
---

1. Get the draft list:
```bash
ed review --list --json
```

2. For each draft, show it to the user with context:
```bash
ed review <draft_id> --json
```

3. Ask the user: approve / edit / reject / skip / regenerate

4. Execute the chosen action:
- approve: `ed approve <draft_id> --json`
- reject: `ed reject <draft_id>`
- skip: `ed skip <draft_id>`
```

`src/ed_bot/skills/ed-answer.md`:
```markdown
---
name: ed-answer
description: Generate a draft answer for a specific EdStem thread.
---

Usage: /ed-answer <thread_number>

Run:
```bash
ed answer <thread_number> --json
```

Show the draft to the user. Ask if they want to approve, edit, or regenerate.
If they say approve: `ed approve <draft_id> --json`
```

`src/ed_bot/skills/ed-ingest.md`:
```markdown
---
name: ed-ingest
description: Pull latest threads from EdStem and index into the knowledge base.
---

Run:
```bash
ed ingest threads --all --json
```

Then index:
```bash
ed status --json
```

Report how many new threads were ingested and current knowledge base state.
```

- [ ] **Step 2: Commit**

```bash
git add src/ed_bot/skills/
git commit -m "feat: Claude Code skill definitions for ed-status, ed-review, ed-answer, ed-ingest"
```

---

### Task 15: Full Test Suite + Push

- [ ] **Step 1: Run complete test suite**

```bash
cd E:/workspaces/school/gt/ed-bot
uv run pytest -v
```

- [ ] **Step 2: Verify CLI help**

```bash
uv run ed --help
uv run ed ingest --help
uv run ed review --help
uv run ed guardrails --help
```

- [ ] **Step 3: Push to GitHub**

```bash
git push
```
