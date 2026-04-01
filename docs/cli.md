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
| `--json` | JSON output |

**Examples:**

```bash
# Ingest a specific semester
ed ingest threads --semester fall2025

# Ingest all configured semesters
ed ingest threads --all

# JSON output
ed ingest threads --semester fall2025 --json
# {"semester": "fall2025", "count": 342}

# Ingest all semesters, JSON
ed ingest threads --all --json
# {"total": 689}
```

### ed ingest projects

Ingest project PDFs or starter code.

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
# │ threads-fall2025     │ 1847   │
# │ projects             │ 234    │
# └──────────────────────┴────────┘
# Drafts pending: 3

ed status --json
# {"course_id": 12345, "collections": {"threads-fall2025": {"chunk_count": 1847}}, "drafts_pending": 3}
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
