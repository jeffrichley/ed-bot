# ed-bot — EdStem Forum Automation

This project automates answering student questions on EdStem for GT CS 7646 (ML4T).

## Skills

The following skills are available in `.claude/skills/`:

- `/ed-check` — Scan the forum, classify threads, draft answers interactively
- `/ed-answer <thread#>` — Draft an answer for a specific thread
- `/ed-status` — Quick forum dashboard
- `/ed-ingest` — Pull new content and re-index

## Working Directory

All CLI commands that need the `.env` file (API tokens) should run from:
```
E:\workspaces\school\gt\ed
```

## Key Directories

- `~/.ed-bot/config.yaml` — Course configuration
- `~/.ed-bot/knowledge/` — Ingested markdown files (threads, projects, lectures, canvas)
- `~/.ed-bot/playbook/` — Style guide + per-project guardrails
- `~/.ed-bot/pyqmd/` — pyqmd search index

## CLI Tools

- `ed-api` — EdStem API client (threads, comments, lessons, files)
- `ed` — ed-bot CLI (ingest, index, contextualize, review, answer)
- `qmd` — pyqmd search engine (search, index, graph)

## Rules

1. NEVER provide solution code for graded assignments
2. Check per-project guardrails before drafting any answer
3. Follow the style guide for tone (Socratic for conceptual, direct for logistics, etc.)
4. Post answers with `--answer` flag, not as plain comments
5. When unsure, flag for human review rather than guessing
