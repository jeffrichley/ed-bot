# Project Ingestion

Project requirements are pulled directly from Canvas LMS. The Canvas ingester fetches assignment HTML, converts it to clean markdown, and stores it alongside other knowledge base content. Legacy PDF-based ingestion is also supported for courses not using Canvas.

## Canvas ingestion (primary method)

`ed ingest canvas` pulls assignments, pages, and announcements from a Canvas course in a single command. See the [Canvas Integration Guide](canvas.md) for full details.

```bash
ed ingest canvas 498126
```

Project requirements are saved to `{data_dir}/projects/`:

```
~/.ed-bot/knowledge/projects/
├── project1-requirements.md
├── project2-requirements.md
├── project3-requirements.md
└── ...
```

### Preview before ingesting

Use `--list` to see what assignments are available without downloading:

```bash
ed ingest canvas 498126 --list
```

```
Canvas assignments for course 498126:
  [123456] Project 1: DTDP (due 2025-09-07)
  [123457] Project 2: Optimize Something (due 2025-09-21)
  [123458] Project 3: Assess Learners (due 2025-10-05)
  ...
```

### Selective ingestion

By default, `ed ingest canvas` fetches assignments matching a filter. Pass `--filter ""` to pull all assignments regardless of name:

```bash
ed ingest canvas 498126 --filter ""
```

## Frontmatter format

Canvas-sourced project files include provenance metadata:

```yaml
---
project: "Project 2"
type: requirements
source: canvas
canvas_assignment_id: 123457
canvas_course_id: 498126
ingested: 2025-09-01T10:00:00+00:00
---
```

The full converted markdown follows.

## Legacy PDF ingestion

For courses where requirements are distributed as PDFs rather than Canvas assignments, `ed ingest projects` is still available:

```bash
ed ingest projects PATH [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `PATH` | Path to a PDF file or a directory of `.py` files |
| `--name TEXT` | Project name (defaults to filename stem) |
| `--type TEXT` | `auto`, `requirements`, or `starter-code` (default: `auto`) |
| `--json` | Output JSON |
| `--bot-dir PATH` | Override bot directory |

### PDF examples

Ingest a requirements PDF:

```bash
ed ingest projects ~/assignments/project2.pdf --name "Project 2"
# Ingested 1 files for Project 2.
```

Ingest a directory of starter code:

```bash
ed ingest projects ~/assignments/project2/starter/ --name "project2"
# Ingested 4 files for project2.
```

### PDF conversion

The ingester uses [markitdown](https://github.com/microsoft/markitdown) to convert PDFs to markdown. If markitdown fails (e.g., a scanned image PDF), it falls back to raw text extraction.

### Starter code ingestion

For Python files, each `.py` file is wrapped in a markdown code fence with identifying frontmatter:

```yaml
---
project: "project2"
type: starter-code
file: analysis.py
ingested: 2025-09-01T10:01:00+00:00
---

# analysis.py (Starter Code)

```python
def analyze_portfolio(prices):
    ...
```
```

!!! info "Why index starter code?"
    Having the starter code in the knowledge base lets the answer engine recognize when a student is confused about a specific function signature, tell whether their approach matches the expected structure, and avoid accidentally revealing implementation details that go beyond the starter scaffold.

## Project slug naming

The ingester derives a URL-safe slug from the project name:

| Project name | Slug |
|-------------|------|
| `Project 1` | `project-1` |
| `project2` | `project2` |
| `ML4T Final` | `ml4t-final` |

The guardrails system uses the same slug to locate `{guardrails_dir}/{slug}.md`.

## After ingestion

Run `ed index` to load project content into the vector store:

```bash
ed ingest canvas 498126
ed index
```
