# ed-bot: EdStem Forum Automation — Design Spec

## Overview

An automation system for answering questions on the EdStem forum for Georgia Tech's
CS 7646 Machine Learning for Trading (and other OMSCS courses). Generates draft
answers for faculty review, with a path to full automation.

The system ingests historical Q&A threads, project materials, and lecture transcripts
into a searchable knowledge base (powered by pyqmd), then uses that context plus
per-project guardrails to draft responses.

## Tech Stack

| Component | Choice |
|-----------|--------|
| Package manager | uv |
| CLI framework | Typer |
| Logging | Rich |
| Output modes | Rich (human) / JSON (machine, via `--json` flag) |
| Knowledge base | pyqmd (hybrid BM25 + vector search) |
| EdStem API | ed-api |
| Video transcription | faster-whisper (local, no API cost) |
| Video processing | ffmpeg (frame extraction, scene detection) |
| PDF conversion | markitdown (Microsoft) |
| LLM | Claude API (for draft generation, guardrail generation) |

## Dependencies

```
pyqmd   — standalone, no knowledge of EdStem
ed-api  — standalone EdStem API client
ed-bot  — depends on both above
```

## Configuration

```yaml
# ~/.ed-bot/config.yaml
course_id: 12345
region: us
semesters:
  - name: spring-2026
    course_id: 12345
  - name: fall-2025
    course_id: 11111
  - name: spring-2025
    course_id: 10000
data_dir: ~/.ed-bot/knowledge
playbook_dir: ~/.ed-bot/playbook
draft_queue_dir: ~/.ed-bot/drafts
```

## Subsystem 1: Ingestion

### Thread Ingestion

```bash
ed ingest threads --course 12345 --semester spring-2026
ed ingest threads --course 11111 --semester fall-2025     # historical
ed ingest threads --all                                    # all configured semesters
```

**Process:**
1. Call `ed-api` to list all threads for the course (paginated via `list_all()`)
2. For each thread, fetch full detail (including comments)
3. Convert to structured markdown with YAML frontmatter
4. Write to `~/.ed-bot/knowledge/threads/{semester}/`
5. Index into pyqmd collection `threads-{semester}`

**Thread markdown format:**

```markdown
---
thread_id: 342
thread_number: 42
course_id: 12345
semester: spring-2026
category: "Project 1"
subcategory: "Martingale"
type: question
title: "get_data() returns NaN for first 20 rows"
author_role: student
status: resolved
is_endorsed: true
is_private: false
created: 2026-03-15T10:30:00Z
updated: 2026-03-16T14:22:00Z
comment_count: 3
has_staff_response: true
has_accepted_answer: true
---

# get_data() returns NaN for first 20 rows

I'm calling `get_data()` with symbol='SPY' and start_date='2020-01-01'
but the first 20 rows of my indicator output are NaN. Is this expected?

## Answer by TA (endorsed, accepted)

Yes, this is expected behavior. Your indicator has a 20-day lookback
period (the rolling window), so the first 19 values will be NaN because
there isn't enough historical data to compute the indicator.

Make sure your data starts at least 20 trading days before your actual
analysis start date to account for this warmup period.

## Comment by student

Thank you! I moved my start date back and it works now.

## Comment by student

I had the same issue. For anyone else seeing this, you need to request
extra data before your actual date range.
```

**Incremental ingestion:** Track the latest thread timestamp per semester.
Subsequent runs only fetch threads created/updated after that timestamp.

### Project Ingestion

```bash
ed ingest projects ./project1-requirements.pdf
ed ingest projects ./project1-requirements.pdf --name "Project 1 - Martingale"
ed ingest projects ./project1-code/ --type starter-code
```

**Process:**
1. PDFs: convert to markdown via markitdown
2. Python files: wrap in markdown with code fences and file path headers
3. Write to `~/.ed-bot/knowledge/projects/`
4. Index into pyqmd collection `projects`

**Starter code markdown format:**

```markdown
---
project: "Project 1 - Martingale"
type: starter-code
file: martingale.py
ingested: 2026-04-01T12:00:00Z
---

# martingale.py (Starter Code)

\```python
"""Assess a betting strategy."""

import numpy as np

def get_spin_result(win_prob):
    """Given a win probability, return True or False."""
    result = False
    if np.random.random() <= win_prob:
        result = True
    return result

def test_code():
    """TODO: Implement your strategy here."""
    pass
\```
```

### Lecture Ingestion

```bash
ed ingest lectures --course 12345
ed ingest lectures --course 12345 --lesson "Lesson 01"    # specific lesson
```

**Process:**
1. Fetch lecture/lesson list from EdStem API
2. Download video files (or extract stream URLs)
3. Extract audio via ffmpeg
4. Transcribe via faster-whisper (local Whisper model, no API)
5. Extract key frames at scene changes via ffmpeg scene detection
6. Generate timestamped markdown per lecture
7. Write to `~/.ed-bot/knowledge/lectures/`
8. Index into pyqmd collection `lectures`

**Lecture markdown format:**

```markdown
---
lecture: "Lesson 01 - Reading Data"
course_id: 12345
duration: "45:22"
video_url: "https://edstem.org/..."
transcribed: 2026-04-01T12:00:00Z
---

# Lesson 01: Reading Data

## [00:00] Introduction

Welcome to the first lesson on reading financial data. In this lesson
we'll cover how to use pandas to access historical stock data.

![Slide: Course Overview](./lesson-01/screenshot-00-00-15.png)

## [03:42] Using pandas DataReader

The primary way we'll access stock data is through pandas. Let me show
you how the `get_data()` function works...

![Slide: pandas DataReader API](./lesson-01/screenshot-00-03-42.png)

## [08:15] Handling Missing Data

You'll notice that some trading days have NaN values. This is common
when dealing with financial data...

![Slide: NaN Values in DataFrames](./lesson-01/screenshot-00-08-15.png)
```

**Screenshot storage:** Images stored alongside the markdown file in a
subdirectory named after the lesson. pyqmd indexes the text; the image paths
are preserved so the bot can reference them in answers.

## Subsystem 2: Playbook & Guardrails

### Playbook (global style guide)

Located at `~/.ed-bot/playbook/style-guide.md`. Created once, edited by the
instructor. Defines voice, tone rules, and response patterns.

```markdown
# Ed-Bot Style Guide

## Voice

You are a helpful teaching assistant for CS 7646 Machine Learning for Trading
at Georgia Tech. You are knowledgeable, patient, and encouraging.

## Tone by Question Type

### Logistics (deadlines, setup, grading)
- Be direct and factual
- Include specific dates, links, or steps
- No Socratic method needed — just answer the question

### Conceptual (theory, "why does X work this way?")
- Use Socratic approach: ask guiding questions before giving the answer
- Point to relevant lectures or readings
- Build understanding, don't just provide facts

### Project Help (debugging, "my code doesn't work")
- Never provide solution code
- Ask what they've tried
- Point to relevant concepts and documentation
- If their approach is fundamentally wrong, redirect gently
- Reference similar past threads when applicable

### Teaching Moments (deep explanations)
- Be thorough — these are opportunities to educate
- Use examples, analogies, and step-by-step reasoning
- Reference lecture content with timestamps when possible
- Include relevant visualizations or diagrams if helpful

## General Rules
- Never provide complete solutions to graded assignments
- Always be respectful and encouraging
- If uncertain about an answer, say so rather than guessing
- Reference course materials (lectures, project docs) when possible
- Keep responses focused — answer what was asked
```

### Per-Project Guardrails

```bash
ed guardrails generate --project "Project 1"    # auto-generate from project docs
ed guardrails edit --project "Project 1"        # open in $EDITOR
ed guardrails list                               # show all guardrail files
```

**Auto-generation process:**
1. Read the project requirements markdown (from ingested projects)
2. Read the starter code markdown
3. Use LLM to analyze and produce:
   - "Never reveal" list (solution-specific implementation details)
   - "OK to discuss" list (general concepts, public API usage)
   - "Common questions to redirect" (patterns with suggested approaches)
4. Write to `~/.ed-bot/playbook/guardrails/{project-name}.md`
5. Faculty reviews and edits the generated file

**Guardrail file format:**

```markdown
---
project: "Project 1 - Martingale"
guardrail_level: strict
auto_generated: 2026-04-01T12:00:00Z
reviewed_by: null
---

# Project 1 - Martingale: Guardrails

## Never Reveal
- The specific implementation of the betting strategy in `test_code()`
- Exact expected values for experiment results
- The stopping condition logic
- Complete numpy array manipulation for tracking winnings

## OK to Discuss
- General concept of the Martingale strategy (it's public knowledge)
- How `numpy.random` works (general Python, not project-specific)
- How to use matplotlib for plotting (general skill)
- How to read the project requirements document
- General debugging approaches (print statements, checking array shapes)

## Common Questions — Redirect Patterns
- "Is my chart right?" → Ask what they expect to see based on the
  mathematical properties; don't confirm or deny specific values
- "What should the mean be?" → Point to the mathematical expectation
  of the Martingale strategy; let them derive the value
- "My episode ends early" → Ask about their stopping condition logic
  without revealing what it should be
- "How do I track winnings?" → Suggest using a numpy array and thinking
  about what value to store at each step; don't give the indexing pattern
```

## Subsystem 3: Answer Engine

### Thread Status Classification

The bot determines thread status from EdStem data:

| Status | Criteria | In Queue? |
|--------|----------|-----------|
| `unanswered` | Zero comments | Yes (highest priority) |
| `student_only` | Comments exist, none from staff, no endorsement | Yes (high priority) |
| `needs_followup` | Staff answered, student replied after staff | Yes (medium priority) |
| `endorsed` | Student answer endorsed by staff | No |
| `staff_answered` | At least one staff comment, no student follow-up | No |
| `resolved` | Marked resolved in EdStem | No |
| `private_flagged` | Detected as potential integrity issue | Yes (immediate, suggest mark private) |

**Role detection:** Use EdStem course roles (staff/admin = faculty, student = student).
If roles are unreliable, fall back to a configured list of staff user IDs in config.yaml.

### Question Classification

When processing a thread, the bot classifies the question type:

| Type | Detection Signals | Response Template |
|------|-------------------|-------------------|
| `logistics` | Due dates, deadlines, submission, grading, extensions | Direct, factual |
| `setup` | Installation, environment, import errors, tooling | Step-by-step |
| `conceptual` | "Why does...", "how does...", "explain...", theory questions | Socratic |
| `project_help` | References a project name + code/output/error | Soft redirect per guardrails |
| `teaching_moment` | Broad concept question, multiple students interested | Thorough explanation |
| `integrity_risk` | Contains code that looks like a solution attempt | Flag, suggest private |

Classification is done via LLM (not keyword matching) so it can handle nuance —
e.g., "my Bollinger Band code crashes" is `project_help` even though "crash" might
suggest `setup`. The LLM sees the full thread context when classifying.

### Draft Generation Pipeline

```
1. Receive thread (from queue scan or inline request)
       │
       ▼
2. Classify thread status (unanswered / student_only / needs_followup)
       │
       ▼
3. Classify question type (logistics / setup / conceptual / project / teaching)
       │
       ▼
4. Identify project context (if any) → load guardrails file
       │
       ▼
5. Retrieve relevant context from pyqmd:
   a. Search threads-* collections for similar past Q&A
      (prioritize endorsed/accepted answers)
   b. Search projects collection for relevant requirements/code
   c. Search lectures collection for relevant transcript sections
       │
       ▼
6. Build LLM prompt:
   - System: style guide + guardrails + response template
   - Context: retrieved chunks (past answers, docs, transcripts)
   - User: the student's question + any existing comments
       │
       ▼
7. Generate draft via Claude API
       │
       ▼
8. Store draft in queue:
   ~/.ed-bot/drafts/{draft_id}.json
   {
     "draft_id": "abc123",
     "thread_id": 342,
     "thread_number": 42,
     "thread_title": "get_data() returns NaN",
     "thread_status": "unanswered",
     "question_type": "project_help",
     "project": "Project 1",
     "priority": "high",
     "content": "The NaN values you're seeing are expected...",
     "context_used": ["threads/spring-2025/0142-nan-values.md", ...],
     "guardrails_applied": "project1.md",
     "created": "2026-04-01T14:30:00Z"
   }
```

### Review Queue

**Batch mode (human):**

```bash
ed review                                    # show next highest priority draft
ed review --list                             # list all pending drafts
ed review --list --project "Project 1"       # filter by project
ed review --list --status unanswered         # filter by thread status
ed review --list --type conceptual           # filter by question type
```

**Batch mode (machine):**

```bash
ed review --list --json
# [{"draft_id": "abc123", "thread_id": 342, "title": "...", "priority": "high", ...}]

ed review abc123 --json
# {"draft_id": "abc123", "content": "...", "context_used": [...], ...}
```

**Actions:**

```bash
ed approve <draft_id>                        # post draft as comment on thread
ed approve <draft_id> --as-answer            # post as answer (not just comment)
ed approve <draft_id> --endorse              # endorse existing student answer instead
ed edit <draft_id>                           # open in $EDITOR, then post
ed reject <draft_id>                         # discard draft
ed reject <draft_id> --reason "off topic"    # discard with reason (for learning)
ed skip <draft_id>                           # move to back of queue
ed private <draft_id>                        # mark thread private + post draft
ed regenerate <draft_id>                     # re-generate with different context
ed regenerate <draft_id> --hint "focus on the lookback period"  # guided re-gen
```

**Inline mode:**

```bash
ed answer 342                                # draft answer for thread 342
ed answer 342 --json                         # same, JSON output
ed answer 12345:42                           # by course:thread_number
```

**Quick actions (no draft needed):**

```bash
ed endorse 342                               # endorse the best comment on thread 342
ed endorse 342 --comment 98765               # endorse a specific comment
ed private 342                               # mark thread private
```

### Forum Status

```bash
ed status                                    # overview of forum state
ed status --json                             # machine-readable

# Human output:
# Course: CS 7646 ML4T (Spring 2026)
# ┌──────────────────┬───────┐
# │ Unanswered       │    12 │
# │ Student-only     │     8 │
# │ Needs follow-up  │     3 │
# │ Drafts pending   │     5 │
# │ Total threads    │ 1,247 │
# └──────────────────┴───────┘
```

## Claude Code Skills

Skills invoke the CLI with `--json` and present results conversationally.

### /ed-status

Shows current forum state. Entry point for a review session.

```
You: /ed-status
Bot: Forum overview for CS 7646 Spring 2026:
     - 12 unanswered threads (5 from today)
     - 8 threads with student-only answers awaiting review
     - 3 threads needing follow-up
     - 5 drafts pending your review
     Want me to start with the review queue?
```

### /ed-review

Batch review workflow. Presents drafts one at a time with context.

```
You: /ed-review
Bot: Draft for thread #42: "get_data() returns NaN for first 20 rows"
     Category: Project 1 | Type: project_help | Priority: high

     Student's question: [shows question]

     My draft:
     [shows draft answer]

     Based on: 3 similar past threads (spring-2025 #142, fall-2025 #87, #201)

     Actions: approve / edit / reject / skip / regenerate
```

### /ed-answer <thread>

Inline drafting for a specific thread.

```
You: /ed-answer 42
Bot: Thread #42: "get_data() returns NaN for first 20 rows"
     [shows full thread with existing comments]

     Classified as: project_help (Project 1)
     Guardrails: project1.md loaded

     Draft answer:
     [shows draft]

     Shall I post this, or would you like to edit it?
```

### /ed-ingest

Pull and index new content.

```
You: /ed-ingest
Bot: Pulling threads since last sync (2026-03-31)...
     Found 47 new/updated threads.
     Indexed into pyqmd collection threads-spring-2026.
     Knowledge base updated.
```

## Data Storage Layout

```
~/.ed-bot/
├── config.yaml                          # Course config, API settings
├── knowledge/                           # Ingested content (markdown files)
│   ├── threads/
│   │   ├── spring-2026/
│   │   │   ├── 0001-how-to-install.md
│   │   │   └── ...
│   │   ├── fall-2025/
│   │   └── spring-2025/
│   ├── projects/
│   │   ├── project1-requirements.md
│   │   ├── project1-starter-code.md
│   │   └── ...
│   └── lectures/
│       ├── lesson-01-reading-data.md
│       ├── lesson-01-reading-data/
│       │   ├── screenshot-00-03-42.png
│       │   └── ...
│       └── ...
├── playbook/                            # Style guide + guardrails
│   ├── style-guide.md
│   └── guardrails/
│       ├── project1.md
│       ├── project2.md
│       └── ...
├── drafts/                              # Review queue
│   ├── abc123.json
│   └── ...
└── state/                               # Sync state
    ├── last-sync.json                   # Per-semester last sync timestamps
    └── draft-history.json               # Approved/rejected draft log (for learning)
```

## Future: Monitoring Service

Not in scope for initial build, but the architecture supports it:

```bash
ed monitor --interval 5m                 # poll every 5 minutes
ed monitor --daemon                      # run as background service
```

Would watch for new unanswered threads, auto-generate drafts, and notify
via desktop notification or Slack webhook. The review queue would fill up
automatically, and the instructor reviews when ready.

## Project Structure

```
ed-bot/
├── pyproject.toml
├── README.md
├── src/
│   └── ed_bot/
│       ├── __init__.py
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── main.py              # Typer app: `ed` command
│       │   ├── ingest.py            # ed ingest subcommands
│       │   ├── review.py            # ed review subcommands
│       │   ├── answer.py            # ed answer command
│       │   ├── status.py            # ed status command
│       │   ├── guardrails.py        # ed guardrails subcommands
│       │   └── output.py            # Shared Rich/JSON output helpers
│       ├── ingestion/
│       │   ├── __init__.py
│       │   ├── threads.py           # Thread ingestion pipeline
│       │   ├── projects.py          # Project doc ingestion
│       │   ├── lectures.py          # Video download + transcription
│       │   └── markdown.py          # Thread/project → markdown conversion
│       ├── knowledge/
│       │   ├── __init__.py
│       │   ├── collections.py       # pyqmd collection management
│       │   └── retrieval.py         # Context retrieval for answer generation
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── classifier.py        # Thread status + question type classification
│       │   ├── drafter.py           # Draft generation (LLM + context + guardrails)
│       │   ├── guardrails.py        # Guardrail loading + auto-generation
│       │   └── templates.py         # Response templates by question type
│       ├── queue/
│       │   ├── __init__.py
│       │   ├── manager.py           # Draft queue CRUD
│       │   └── priority.py          # Priority scoring
│       ├── skills/                   # Claude Code skill definitions
│       │   ├── ed-status.md
│       │   ├── ed-review.md
│       │   ├── ed-answer.md
│       │   └── ed-ingest.md
│       └── config.py                # Configuration management
├── tests/
│   ├── test_classifier.py
│   ├── test_drafter.py
│   ├── test_ingestion.py
│   └── fixtures/
│       ├── sample_threads/
│       └── sample_projects/
└── docs/
    └── ...
```

## References

- [edstem-mcp](https://github.com/rob-9/edstem-mcp) — 22-tool MCP server for EdStem.
  Reference for endpoint coverage and markdown→XML conversion.
- [edapi](https://github.com/smartspot2/edapi) — Existing Python client (incomplete).
  Reference for API endpoint URLs and Ed XML document format.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — CTranslate2-based
  Whisper implementation. 4x faster than openai-whisper with same accuracy.
- [markitdown](https://github.com/microsoft/markitdown) — Microsoft's document-to-markdown
  converter. Handles PDF, DOCX, PPTX.
- [pyqmd](https://github.com/jeffrichley/pyqmd) — The knowledge base engine this project
  depends on.
