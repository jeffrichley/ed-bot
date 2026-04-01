# Project Ingestion

`ProjectIngester` converts project materials into indexed markdown so the answer engine can retrieve course-specific context. It handles two input types: PDF requirement documents and Python starter code.

## Command

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

### Examples

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

JSON output:

```bash
ed ingest projects project1.pdf --name "Project 1" --json
# {"project": "Project 1", "count": 1}
```

## PDF conversion

The ingester uses [markitdown](https://github.com/microsoft/markitdown) to convert PDFs to markdown. If markitdown fails (e.g., a scanned image PDF), it falls back to raw text extraction.

Output files are stored in `{projects_dir}/`:

```
~/.ed-bot/knowledge/projects/project-2-requirements.md
```

### PDF frontmatter format

```yaml
---
project: "Project 2"
type: requirements
source: "project2.pdf"
ingested: 2025-09-01T10:00:00+00:00
---
```

The full converted markdown follows.

## Starter code ingestion

For Python files, each `.py` file is wrapped in a markdown code fence with identifying frontmatter. Passing a directory recurses through all `**/*.py` files:

```bash
ed ingest projects ./project2/starter --name "project2"
```

Output per file:

```
~/.ed-bot/knowledge/projects/project2-analysis.md
~/.ed-bot/knowledge/projects/project2-optimization.md
```

### Starter code format

```yaml
---
project: "project2"
type: starter-code
file: analysis.py
ingested: 2025-09-01T10:01:00+00:00
---

# analysis.py (Starter Code)

```python
# Your code here
def analyze_portfolio(prices):
    ...
```
```

!!! info "Why index starter code?"
    Having the starter code in the knowledge base lets the answer engine recognize when a student is confused about a specific function signature, tell whether their approach matches the expected structure, and avoid accidentally revealing implementation details that go beyond the starter scaffold.

## Project slug naming

The ingester derives a URL-safe slug from the project name by lowercasing and replacing non-alphanumeric characters with hyphens:

| Project name | Slug |
|-------------|------|
| `Project 1` | `project-1` |
| `project2` | `project2` |
| `ML4T Final` | `ml4t-final` |

The guardrails system uses the same slug to locate `{guardrails_dir}/{slug}.md`.

## Knowledge base indexing

Project files are indexed into the `projects` pyqmd collection. The collection is created automatically if it does not exist:

```python
kb = KnowledgeBase(config)
kb.index_projects()
```
