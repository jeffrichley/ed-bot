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
6. **Run `/humanizer` on every drafted forum answer before showing it to the
   user.** No exceptions. The pre-humanizer draft is internal — only the
   humanizer's final output is ever presented or posted. The `ed-check` and
   `ed-answer` skills both have a MANDATORY Step 5b for this; do not skip it
   on the rationalization that "the draft already sounds fine."

## Troubleshooting

If `ed` crashes with `ModuleNotFoundError` (e.g. `No module named 'tomli_w'`),
the global `uv tool` snapshot is stale relative to the workspace source.
Refresh it:

```
uv tool install --reinstall E:\workspaces\school\gt\ed-bot
```

## Session start behavior

When starting a Claude Code session in this project, proactively invoke
`/ed-watch start` to launch the forum watcher in the background. Skip if:
- The user explicitly says not to watch this session, OR
- The user is opening the project for unrelated work (e.g., debugging the
  ingest pipeline), OR
- `~/.ed-bot/config.yaml` has no `course_id` (between semesters).

The watcher is silent on normal startup; it only alerts when an actionable
event fires. Stopping is automatic when the Claude session ends, or manual
via `/ed-watch stop`.
