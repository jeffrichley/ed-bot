---
name: ed-watch
description: Start/stop the ed-watch background forum watcher. Launches `ed watch` in the background, attaches Claude Code's Monitor tool to its stdout, and reports event-kind sound mapping. Use this at session start (per CLAUDE.md) or whenever the user says "watch the forum" / "start watching."
---

# EdStem Forum Watcher

`ed watch` polls the active EdStem course on a schedule defined in
`~/.ed-bot/watch.yaml` and alerts (sound + chat notification) only when an
*actionable* event happens. See `docs/superpowers/specs/2026-05-28-ed-watch-design.md`
for the full design.

## Subcommands

- `start` — launch the watcher in the background and attach Monitor.
- `stop` — signal the running watcher to shut down cleanly.

## Phase 1: `start`

### Step 1: Check it isn't already running

```bash
cd E:\workspaces\school\gt\ed
ed watch status
```

If output contains "is running", skip to step 3 (Monitor attach) — the
background process is already up.

### Step 2: Launch in background

Use Claude Code's `Bash` tool with `run_in_background=true`:

```bash
cd E:\workspaces\school\gt\ed
ed watch
```

The watcher's stdout is the event stream.

### Step 3: Attach Monitor

Use the `Monitor` tool, persistent=true, pointing at the background task's
output. The watcher emits one JSON line per actionable event:

```
{"kind": "new_thread"|"followup"|"escalation"|"error"|"recovered",
 "thread_id": ..., "number": ..., "title": ...,
 "category": ..., "url": ..., "ts": ...}
```

Each event line becomes a chat notification. Sounds play locally regardless of
whether Monitor is attached.

### Step 4: Confirm with the user

Print:

```
ed-watch is now running.
Sounds (played locally):
  new_thread  — distinct sound for actionable new questions
  followup    — distinct sound for follow-ups on our answers
  escalation  — distinct sound for medical/integrity/regrade keywords
  error       — distinct sound after 30 min of API failures

Chat notifications will appear here when actionable events fire.
```

## Phase 2: `stop`

### Step 1: Stop the daemon

```bash
ed watch stop
```

### Step 2: Detach the Monitor

Call TaskStop on the Monitor task.

## Rules

1. Never start the watcher twice — check `ed watch status` first.
2. Sound files are configured in `~/.ed-bot/watch.yaml`; do not edit them
   without explicit user instruction.
3. The watcher reuses the existing tracker DB but writes to its own
   `watch_alerts` table; it does NOT interfere with `/ed-check`'s state.
