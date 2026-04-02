<div class="iris-hero" markdown>

# ed-bot

EdStem forum automation for GT ML4T and beyond.

</div>

<div class="iris-cards" markdown>

<div class="iris-card" markdown>

### Knowledge Base

Powered by [pyqmd](https://github.com/jeffrichley/py-qmd). **36,526 chunks** indexed across 8,345 threads (5 semesters), 11 project requirements, 22 Canvas pages, 21 announcements, and 333 lecture transcripts — giving every draft answer grounded, course-specific context.

</div>

<div class="iris-card" markdown>

### Canvas Ingestion

Pull project requirements, course policy pages, and announcements directly from Canvas LMS. HTML is automatically converted to clean markdown and stored alongside thread and lecture content.

</div>

<div class="iris-card" markdown>

### Lecture Pipeline

Full video pipeline: download from Kaltura via `yt-dlp`, transcribe with `faster-whisper`, and generate indexed markdown with full provenance — lesson ID, slide ID, and EdStem deep links. Skips already-ingested lectures automatically.

</div>

<div class="iris-card" markdown>

### Contextual Retrieval

`ed contextualize` generates search context for every knowledge base file using Ollama (llama3.2 by default). Async concurrent processing delivers an **8x speedup** and is fully resumable — safe to stop and restart at any point.

</div>

<div class="iris-card" markdown>

### Smart Classification

`ThreadClassifier` assigns each thread a `ThreadStatus` (unanswered, student_only, needs_followup, endorsed, staff_answered, resolved, private_flagged) and computes a numeric priority score so the highest-need threads surface first.

</div>

<div class="iris-card" markdown>

### Per-Project Guardrails

`GuardrailsManager` loads project-specific markdown files that define what Claude may never reveal, what is okay to discuss, and common patterns for a given assignment. Auto-detection matches questions to the right guardrail file.

</div>

<div class="iris-card" markdown>

### Draft Review Queue

`DraftQueue` persists drafts as JSON files. Each draft carries its thread context, question type, priority, and applied guardrails. Approve, reject, or skip from the CLI or a Claude Code skill.

</div>

<div class="iris-card" markdown>

### Claude Code Skills

First-class `/ed-status`, `/ed-review`, `/ed-answer`, and `/ed-ingest` skills let teaching assistants manage the forum directly from their editor without switching to a terminal.

</div>

<div class="iris-card" markdown>

### Dual-Mode CLI

Every command supports `--json` output for scripting alongside human-readable rich output. The `ed` entry point exposes `ingest`, `contextualize`, `index`, `status`, `review`, `answer`, and `guardrails` sub-commands.

</div>

</div>

## Workflow

The full ed-bot pipeline — from raw content to ready-to-review drafts:

```
┌──────────────────────────────────────────────┐
│              INGEST                          │
│  ed ingest threads --all                     │
│  ed ingest canvas  <course_id>               │
│  ed ingest lectures --course <id>            │
└────────────────────┬─────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────┐
│              CONTEXTUALIZE & INDEX           │
│  ed contextualize                            │
│  ed index                                    │
└────────────────────┬─────────────────────────┘
                     │
                     ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  ed answer  │────▶│  ed review   │────▶│  approve /  │
│  <thread>   │     │    --list    │     │  reject     │
└─────────────┘     └──────────────┘     └─────────────┘
```

**1. Ingest** — pull threads, Canvas content, and lecture transcripts:

```bash
ed ingest threads --all
ed ingest canvas 498126
ed ingest lectures --course 91346
```

**2. Contextualize** — generate retrieval context for every file using Ollama:

```bash
ed contextualize
```

**3. Index** — load all content into the pyqmd vector store:

```bash
ed index
```

**4. Answer** — generate a draft for an unanswered thread:

```bash
ed answer 98765
# → Draft saved: a3f9c12b0011
```

**5. Review and approve** — inspect the draft and post to EdStem:

```bash
ed review
ed review approve a3f9c12b0011 --as-answer
```

## Next Steps

- [Install ed-bot](getting-started/installation.md)
- [Configure your bot directory](getting-started/configuration.md)
- [Run through the Quick Start](getting-started/quickstart.md)
