# CLI Reference

The `ed` command is the primary interface for ed-bot. Every sub-command supports `--bot-dir PATH` to override the default `~/.ed-bot` directory and `--json` for machine-readable output.

## Global options

| Option | Default | Description |
|--------|---------|-------------|
| `--bot-dir PATH` | `~/.ed-bot` | Bot configuration directory |
| `--help` | — | Show help for any command |

---

## ed ingest

Ingest content into the knowledge base.

### ed ingest threads

Pull all threads from EdStem for a semester.

```bash
ed ingest threads [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--semester TEXT` | Semester name (e.g. `fall2025`) |
| `--course INT` | Course ID (overrides config) |
| `--all` | Ingest all semesters in config |
| `--force` | Re-download all threads, ignoring last-sync timestamp |
| `--json` | JSON output |

**Examples:**

```bash
# Ingest a specific semester (incremental)
ed ingest threads --semester fall2025

# Ingest all configured semesters
ed ingest threads --all

# Force re-download of all threads
ed ingest threads --all --force

# JSON output
ed ingest threads --semester fall2025 --json
# {"semester": "fall2025", "count": 342}

# Ingest all semesters, JSON
ed ingest threads --all --json
# {"total": 689}
```

### ed ingest canvas

Pull project requirements, pages, and announcements from Canvas LMS.

```bash
ed ingest canvas COURSE_ID [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `COURSE_ID` | Canvas course ID |
| `--list` | Preview available assignments without downloading |
| `--filter TEXT` | Only ingest assignments whose name contains this string (default: `"Project"`) |
| `--bot-dir PATH` | Override bot directory |

**Examples:**

```bash
# Preview available assignments
ed ingest canvas 498126 --list

# Ingest project assignments (default filter: "Project")
ed ingest canvas 498126

# Ingest all assignments regardless of name
ed ingest canvas 498126 --filter ""

# Ingest only assignments matching a custom filter
ed ingest canvas 498126 --filter "Indicator"
```

### ed ingest lectures

Download Kaltura lecture videos, transcribe them, and generate indexed markdown.

```bash
ed ingest lectures [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--course INT` | Kaltura course ID |
| `--force` | Re-ingest already-processed lectures |
| `--bot-dir PATH` | Override bot directory |

**Examples:**

```bash
# Ingest all lectures for a course
ed ingest lectures --course 91346

# Force re-download and re-transcription
ed ingest lectures --course 91346 --force
```

### ed ingest projects

Ingest project PDFs or starter code (legacy — prefer `ed ingest canvas`).

```bash
ed ingest projects PATH [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `PATH` | Path to a PDF or directory of `.py` files |
| `--name TEXT` | Project name (default: filename stem) |
| `--type TEXT` | `auto`, `requirements`, `starter-code` |
| `--json` | JSON output |

**Examples:**

```bash
# Ingest a requirements PDF
ed ingest projects ~/assignments/project2.pdf --name "Project 2"

# Ingest starter code directory
ed ingest projects ~/assignments/project2/starter/ --name "project2"

# JSON output
ed ingest projects project1.pdf --json
# {"project": "project1", "count": 1}
```

---

## ed contextualize

Generate contextual retrieval context for knowledge base files using Ollama.

```bash
ed contextualize [SUBCOMMAND] [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `-d, --directory TEXT` | all | Process only this subdirectory (repeatable) |
| `--force` | off | Regenerate already-processed files |
| `--model TEXT` | `llama3.2` | Ollama model to use |
| `-j, --concurrency INT` | `8` | Number of concurrent Ollama requests |
| `--bot-dir PATH` | `~/.ed-bot` | Override bot directory |

**Examples:**

```bash
# Contextualize all knowledge base files
ed contextualize

# Process specific directories only
ed contextualize -d threads -d projects

# Force regeneration
ed contextualize --force

# Use a different model
ed contextualize --model llama3.1

# Increase concurrency for faster processing
ed contextualize -j 16

# Check progress
ed contextualize status
```

---

## ed index

Index all knowledge base content into the pyqmd vector store.

```bash
ed index [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--force` | Force re-index all collections |
| `--bot-dir PATH` | Override bot directory |

Indexes: threads (per semester), projects, lectures, Canvas pages, and announcements.

**Examples:**

```bash
# Index all content
ed index

# Force re-index
ed index --force
```

---

## ed status

Show knowledge base and queue status.

```bash
ed status [OPTIONS]
```

**Example:**

```bash
ed status
# Course: 12345
# ┌──────────────────────┬────────┐
# │ Collection           │ Chunks │
# ├──────────────────────┼────────┤
# │ threads-fall2025     │ 8345   │
# │ projects             │  234   │
# │ lectures             │  333   │
# │ canvas-pages         │   22   │
# │ announcements        │   21   │
# └──────────────────────┴────────┘
# Drafts pending: 3

ed status --json
# {"course_id": 12345, "collections": {"threads-fall2025": {"chunk_count": 8345}}, "drafts_pending": 3}
```

---

## ed answer

Generate a draft answer for a specific thread.

```bash
ed answer THREAD_REF [OPTIONS]
```

| Argument/Option | Description |
|----------------|-------------|
| `THREAD_REF` | Thread ID (`98765`) or `course_id:number` (`12345:312`) |
| `--hint TEXT` | Instructor guidance injected into the prompt |
| `--json` | JSON output |

**Examples:**

```bash
# By thread ID
ed answer 98765

# By course and thread number
ed answer 12345:312

# With instructor hint
ed answer 98765 --hint "The student is confused about axis=0 vs axis=1"

# JSON output
ed answer 98765 --json
# {"draft_id": "a3f9c12b0011", "thread_id": 98765, "thread_number": 312,
#  "title": "...", "status": "unanswered", "project": "project2", "content": "..."}
```

---

## ed review

Review and act on draft answers.

### ed review (show next draft)

```bash
ed review [DRAFT_ID] [OPTIONS]
```

With no arguments, shows the highest-priority pending draft. Pass a draft ID to show a specific one.

| Option | Description |
|--------|-------------|
| `DRAFT_ID` | Specific draft to show |
| `--list` | List all pending drafts |
| `--project TEXT` | Filter by project slug |
| `--status TEXT` | Filter by thread status |
| `--type TEXT` | Filter by question type |
| `--json` | JSON output |

**Examples:**

```bash
# Show next draft
ed review

# Show specific draft
ed review a3f9c12b0011

# List all drafts
ed review --list

# Filter by project
ed review --list --project project2

# List as JSON
ed review --list --json
# [{"draft_id": "a3f9c12b0011", "thread_id": 98765, ...}, ...]
```

### ed review approve

Post a draft to EdStem and remove it from the queue.

```bash
ed review approve DRAFT_ID [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--as-answer` | Post as an answer (marks thread answered) |
| `--endorse` | Endorse an existing student answer instead |
| `--json` | JSON output |

**Examples:**

```bash
# Post as a comment
ed review approve a3f9c12b0011

# Post as an answer
ed review approve a3f9c12b0011 --as-answer

# Endorse a student answer
ed review approve a3f9c12b0011 --endorse

# JSON output
ed review approve a3f9c12b0011 --json
# {"status": "posted", "draft_id": "a3f9c12b0011", "thread_id": 98765}
```

### ed review reject

Discard a draft permanently.

```bash
ed review reject DRAFT_ID [--reason TEXT]
```

**Example:**

```bash
ed review reject a3f9c12b0011 --reason "Guardrail violation — reveals formula"
```

### ed review skip

Push a draft to the back of the queue (sets priority to `low`).

```bash
ed review skip DRAFT_ID
```

**Example:**

```bash
ed review skip a3f9c12b0011
```

---

## ed guardrails

Manage per-project guardrail files.

### ed guardrails list

```bash
ed guardrails list [--json]
```

**Example:**

```bash
ed guardrails list
#   project1
#   project2
#   final-project

ed guardrails list --json
# ["project1", "project2", "final-project"]
```

### ed guardrails edit

Open a guardrail file in `$EDITOR`.

```bash
ed guardrails edit PROJECT_SLUG
```

**Example:**

```bash
ed guardrails edit project2
# Opens ~/.ed-bot/playbook/guardrails/project2.md in $EDITOR
```
