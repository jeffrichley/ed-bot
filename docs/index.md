<div class="iris-hero" markdown>

# ed-bot

EdStem forum automation for GT ML4T and beyond.

</div>

<div class="iris-cards" markdown>

<div class="iris-card" markdown>

### Knowledge Base

Powered by [pyqmd](https://github.com/jeffrichley/py-qmd). Indexes past Q&A threads, project requirements, and lecture transcripts into semantic vector collections — giving every draft answer grounded, course-specific context.

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

Every command supports `--json` output for scripting alongside human-readable rich output. The `ed` entry point exposes `ingest`, `status`, `review`, `answer`, and `guardrails` sub-commands.

</div>

</div>

## Workflow

The typical ed-bot session takes five steps:

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  ed ingest  │────▶│  ed answer   │────▶│  ed review  │
│   threads   │     │  <thread_id> │     │   --list    │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                │
                              ┌─────────────────▼──────────────────┐
                              │  ed approve <id>  |  ed reject <id> │
                              └─────────────────────────────────────┘
```

**1. Ingest** — pull all Ed threads for the current semester and store them as structured markdown:

```bash
ed ingest threads --semester fall2025
```

**2. Answer** — generate a draft for an unanswered thread. ed-bot retrieves relevant past threads, project materials, and lecture content, then calls Claude with the active style guide and guardrails:

```bash
ed answer 98765
# → Draft saved: a3f9c12b0011
```

**3. Review** — inspect the highest-priority draft:

```bash
ed review
```

**4. Approve** — post the draft to EdStem as a comment or answer:

```bash
ed review approve a3f9c12b0011 --as-answer
```

**5. Reject or Skip** — discard a bad draft or push it to the back of the queue:

```bash
ed review reject a3f9c12b0011 --reason "Guardrail violation"
ed review skip   a3f9c12b0011
```

## Next Steps

- [Install ed-bot](getting-started/installation.md)
- [Configure your bot directory](getting-started/configuration.md)
- [Run through the Quick Start](getting-started/quickstart.md)
