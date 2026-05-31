# ed-bot Cockpit TUI — Design

**Date:** 2026-05-31
**Status:** Approved (brainstorming), pending implementation plan

## Summary

A terminal cockpit for managing the EdStem forum. Today the workflow runs
through a Claude Code chat: Claude calls `ed`/`ed-api`, drafts answers, runs the
humanizer, and the human approves in chat. The cockpit moves that loop into a
single, nicely formatted TUI where the human types commands, reads formatted
drafts, and acts with one keystroke, while a forum watcher pushes actionable
threads in automatically.

The brain is a Claude Agent SDK session running the existing project skills
(`ed-check`, `ed-answer`, `humanizer`), `CLAUDE.md`, guardrails, and the
`ed`/`ed-api` tools. Nothing about the agent's judgment is reimplemented in app
code — the TUI is a client to the same agent that runs in chat today.

## Goals

- One screen to triage the forum: a live queue of threads needing attention,
  formatted drafts, a chat/command line, and one-key actions.
- The agent auto-drafts actionable threads in the background so a draft is ready
  the moment the human selects a queue item.
- Typed, validated contract between agent and UI (Pydantic), not hand-shaped
  JSON.
- Reuse the existing skills/guardrails/humanizer unchanged.

## Non-Goals

- Standalone operation without the cockpit process running. If the process
  dies, the brain dies; this is an at-the-desk cockpit, not a 24/7 daemon.
- Showing the pre-humanizer draft. The human only ever sees humanized text
  (hard rule from CLAUDE.md). No before/after view.
- A guardrail-rules panel or a posted-history audit panel (features 7 and 8
  were considered and deliberately cut for v1).
- Replacing the agent's reasoning with app-coded logic.

## Architecture

**One Python process, one asyncio event loop, three cooperating tasks.**

1. **UI task (Textual).** Textual is asyncio-native and shares the `rich`
   lineage already in the project deps. Owns the screen and captures keyboard
   input and hotkeys.
2. **Watcher task.** An `async` coroutine that polls EdStem on the configured
   schedule and, on an actionable event, puts a `WatcherEvent` on a shared
   in-memory `asyncio.Queue`. This replaces the standalone `ed watch` process
   and its stdout/emit/Monitor/JSON-line bridge.
3. **Agent task.** A Claude Agent SDK session (authenticated via the user's
   Claude Max plan, i.e. the Claude Code login, not a metered API key). It is
   the single consumer of the queue. It drives the existing skills and streams
   typed results back to the UI.

**Message flow.** Two producers — the human (via the UI) and the watcher — put
messages on one `asyncio.Queue`. The agent task is the single consumer, so
commands and events serialize naturally in arrival order (finish the current
action, then take the next item). All hand-offs are in-memory; there is no IPC,
no socket, no file bridge.

```
            Textual UI task            watcher task
                  | UserCommand              | WatcherEvent
                  v                           v
              +-------------------------------------+
              |        asyncio.Queue                |
              +-------------------------------------+
                                |  (single consumer, serialized)
                                v
              +-------------------------------------+
              |  agent task — Claude Agent SDK      |
              |  skills, guardrails, humanizer,     |
              |  ed / ed-api                        |
              +-------------------------------------+
                                |  typed Pydantic results
                                v
                      Textual widgets render
```

### Design cautions (carried from brainstorming)

- **UI must stay responsive while the agent works.** Agent work runs in its own
  task; a long draft must never block keyboard input or screen updates.
- **The poll must be truly async.** The current `ed-api` client is synchronous.
  Either wrap its calls in a thread executor (`asyncio.to_thread`) or use async
  HTTP, so polling never stalls the event loop. Decision deferred to the plan;
  thread-executor wrapping is the low-risk default.
- **Staleness guard.** Because the agent auto-drafts, it must re-check the
  thread's `is_answered` state immediately before drafting and again before
  posting, so it never drafts or posts on a thread staff already handled. This
  is the exact bug that caused a large stale queue in prior manual sessions.

## The typed contract (Pydantic)

Every message into the agent and every structured result out of it is a Pydantic
model. The agent is configured to return these shapes via the SDK's structured
output, so the UI consumes validated objects and the SDK retries the agent on a
schema mismatch.

**Inbound to agent**

- `UserCommand` — `{ intent: "check_forum" | "open" | "approve" | "edit" |
  "reject" | "flag" | "skip" | "post_canned" | "watcher_ctl" | "freeform",
  thread: int | None, text: str | None }`. Hotkeys and typed natural language
  both normalize into this. `freeform` carries arbitrary chat text for the agent
  to interpret.
- `WatcherEvent` — `{ kind: "new_thread" | "followup" | "escalation" | "error" |
  "recovered", thread_id: int, number: int, title: str, category: str,
  url: str }`. Mirrors today's watcher event shape.

**Outbound from agent → UI**

- `QueueUpdate` — a list of `QueueItem` to reconcile into the left rail.
- `QueueItem` — `{ thread_id, number, title, category, kind, urgency:
  "normal" | "high", draft_state: "drafting" | "ready" | "flagged" | "failed" |
  "none", status: "needs_attention" | "posted" | "dismissed" }`.
- `DraftPayload` — `{ thread_id, number, question: str, body: str,
  is_canned: bool, project: str | None, guardrails_checked: list[str],
  confidence: "HIGH" | "MEDIUM" | "LOW", post_kind: "answer" | "reply",
  target_comment_id: int | None }`. **`body` is always the final,
  post-humanizer text. There is no raw-draft field by construction.**
- `StatusUpdate` — `{ line: str }`. Drives the status bar
  (e.g. "drafting #207… ▸ humanizer ▸ ready").
- `ActionResult` — `{ thread_id, ok: bool, posted_id: int | None,
  accepted: bool, message: str }`.
- `AlertBanner` — `{ thread_id, number, title, text: str }`. Triggers the header
  flash and sound for escalations surfaced inline.

## Screen layout (Layout A)

- **Header bar.** Course + semester, watcher status (live/poll time), counts.
  Hosts the escalation **alert flash** and the **watcher controls**
  (start/stop, mute) — feature 11/12.
- **Left rail — queue.** Threads needing attention, color-coded by kind,
  escalations pinned on top. Each item shows a draft-state indicator (spinner
  while `drafting`, ready marker when done). Arrow keys / click to select.
- **Center — draft viewer.** For the selected thread: the student's question,
  the formatted (humanized) draft, project, guardrails-checked, confidence, and
  the one-key action legend.
- **Bottom — chat + status.** A chat transcript with you/claude turns and a
  command input line, plus a one-line status bar above it showing what the agent
  is doing right now.
- **Modals (occasional, not permanent panels).** Batch review (flip through
  ready drafts as a deck — feature 10) and the canned-response picker
  (feature 9) open as overlays.

## Behavior

### Auto-draft on arrival

When the agent classifies an incoming `WatcherEvent` as actionable, it
immediately runs the draft flow in the background and attaches the finished
`DraftPayload` to the queue item, so selecting the item shows a ready draft.

- The queue item carries a `draft_state`: `drafting` → `ready` (or `flagged` /
  `failed`). The rail shows a spinner while drafting. Selecting an item that is
  still drafting shows "drafting…" until the payload streams in.
- The agent is a single queue-consumer, so drafts are produced one at a time in
  arrival order. If several events land together, later items finish later.
  Acceptable, and it keeps ordering and token use sane.
- **Admin/extension threads do NOT auto-draft a content answer.** They resolve
  to canned-response triage: the queue item arrives with the correct canned
  reply pre-loaded (`DraftPayload.is_canned = true`). Extension requests are
  triaged by reason per the canned-responses playbook
  (`emergency` → forward text; `discretionary` → clarify/Dean-of-Students text;
  unsure → flagged NEEDS HUMAN). See `~/.ed-bot/playbook/canned-responses.md`.
- **Staleness re-check.** Before drafting and again before posting, the agent
  re-checks `is_answered` so it never drafts/posts on an already-handled thread.

### Acting on a draft

One-key actions on the selected draft (feature 4):

- **[a] approve + post.** Agent posts via `ed-api` (`--answer` for top-level,
  `reply` for nested follow-ups), accepts the comment to resolve, returns
  `ActionResult`. Queue item flips to `posted` and drops off the active list.
- **[e] edit.** Human types guidance in chat ("more Socratic"); agent re-runs
  the draft + humanizer and returns a fresh `DraftPayload`.
- **[r] reject.** Discard the draft; dismiss the item.
- **[f] flag.** Mark NEEDS HUMAN; no post.
- **[s] skip.** Leave in queue, move on.

### Humanizer

The humanizer runs inside the agent's draft flow, unconditionally, exactly as
the skills require today. The UI only ever receives the post-humanizer `body`.
There is no path that surfaces pre-humanizer text.

### Commands (chat input)

Typed natural language maps to `UserCommand`. Examples:
"check the forum" → `check_forum`; "answer 207" → `open` (then auto-draft is
likely already done); "post it" → `approve` on the active thread; "make it more
Socratic" → `edit`; anything else → `freeform` for the agent to interpret.

## Features in scope (from the feature buffet)

In: live action queue (1), formatted draft viewer (2), chat/command input (3),
one-key draft actions (4), status bar (5), canned-response picker (9), batch
review (10), watcher controls (11), inline alerts + sound (12).

Cut for v1: humanizer before/after (6), guardrail panel (7), session/posted
history (8).

## Error handling

- **Agent/SDK error during draft.** Queue item → `draft_state: failed` with the
  message surfaced in status; the item stays selectable so the human can retry
  or flag.
- **Post failure.** `ActionResult.ok = false` with the error; queue item stays
  `needs_attention`; nothing is marked resolved.
- **Watcher poll failure.** Mirror today's behavior: tolerate transient
  failures, and after a sustained outage emit an `error`-kind event that the
  agent surfaces as a banner; emit `recovered` when polling resumes.
- **Process death.** Acceptable and expected as an off switch. No persistence of
  in-flight drafts across restarts in v1; the queue rebuilds from a fresh forum
  scan on launch.

## Testing strategy

- **Pydantic models.** Unit tests for each model's validation, including the
  invariant that `DraftPayload` has no raw-draft field.
- **Queue/consumer logic.** Tests that two producers (UserCommand, WatcherEvent)
  serialize correctly through one consumer, and that ordering holds.
- **Auto-draft state machine.** Tests for `draft_state` transitions
  (`drafting → ready/flagged/failed`) and the staleness re-check skipping
  already-answered threads.
- **Command mapping.** Tests that hotkeys and representative natural-language
  inputs normalize to the right `UserCommand`.
- **Agent integration.** A small set of live-or-recorded tests that the agent,
  given a `WatcherEvent`, returns a schema-valid `DraftPayload` with a humanized
  body. UI rendering itself is covered by Textual's testing harness for the
  widget reconciliation from `QueueUpdate`.

## Open questions deferred to the implementation plan

- Async strategy for the synchronous `ed-api` client: thread-executor wrap
  (default) vs. async HTTP.
- Exact Agent SDK session configuration (system prompt assembly from
  `CLAUDE.md` + skills, tool allow-list, structured-output wiring).
- Whether the watcher's existing tracker DB / dedup logic is reused as-is inside
  the watcher task or simplified now that the agent makes the surface/ignore
  judgment.
