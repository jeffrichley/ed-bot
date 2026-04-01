# Claude Code Skills

ed-bot ships Claude Code skills that let teaching assistants manage the EdStem forum directly from their editor. Skills are stored in `.claude/commands/` and invoked with `/ed-*` slash commands.

## Available skills

| Skill | Description |
|-------|-------------|
| `/ed-status` | Show knowledge base and queue status |
| `/ed-ingest` | Ingest threads, projects, or lectures |
| `/ed-answer` | Generate a draft for a specific thread |
| `/ed-review` | Review, approve, or reject pending drafts |

---

## /ed-status

Shows the current state of the knowledge base collections and draft queue.

**Example conversation:**

```
User: /ed-status

Claude: Here's the current ed-bot status:

  Course: 12345

  Knowledge base collections:
  - threads-fall2025: 1,847 chunks
  - projects: 234 chunks

  Draft queue: 3 pending drafts
    [high] a3f9c12b0011 — #312 Why does my portfolio optimizer return NaN?
    [high] b7e2d4f10033 — #287 Error in assess_portfolio output
    [medium] c9a1e8f20044 — #301 Question about Sharpe ratio calculation
```

---

## /ed-ingest

Triggers thread or project ingestion and reports results.

**Example conversations:**

```
User: /ed-ingest threads fall2025

Claude: Ingesting threads for fall2025...

  Done! Ingested 342 threads for fall2025.
  Knowledge base updated: threads-fall2025 now has 1,847 chunks.
```

```
User: /ed-ingest projects ~/assignments/project2.pdf

Claude: Ingesting project2.pdf as project materials...

  Done! 1 file ingested for project2.
  Knowledge base updated: projects collection has 234 chunks.
```

---

## /ed-answer

Fetches a thread, generates a draft, and displays it for immediate review.

**Example conversation:**

```
User: /ed-answer 98765

Claude: Fetching thread #312: "Why does my portfolio optimizer return NaN?"

  Status: unanswered | Project: project2 | Priority: high
  Guardrails: project2.md applied

  --- Draft Answer ---

  Great question! NaN values in portfolio optimization typically come from
  one of a few sources:

  1. **Division by zero in volatility**: If all your daily returns are
     identical, the standard deviation is 0, causing a NaN Sharpe ratio.
     What does `port_std` equal when you print it?

  2. **NaN in input data**: Check whether `get_data()` returned any NaN
     values with `prices.isnull().sum()`.

  3. **Optimization bounds**: Make sure your bounds allow the optimizer
     to find a valid solution.

  What have you tried so far?

  ---

  Draft saved: a3f9c12b0011

  Approve? Type /ed-review approve a3f9c12b0011 --as-answer
```

---

## /ed-review

Shows the pending draft queue and lets you act on individual drafts.

**Example conversations:**

```
User: /ed-review

Claude: 3 drafts pending. Highest priority:

  Draft a3f9c12b0011 [HIGH]
  Thread #312: Why does my portfolio optimizer return NaN?
  Type: project_help | Project: project2
  Context: threads/fall2025/0287-sharpe-nan.md, projects/project2-requirements.md

  --- Draft ---
  Great question! NaN values in portfolio optimization typically come from...
  ---

  Actions:
  - Approve as comment:  /ed-review approve a3f9c12b0011
  - Approve as answer:   /ed-review approve a3f9c12b0011 --as-answer
  - Reject:              /ed-review reject a3f9c12b0011
  - Skip:                /ed-review skip a3f9c12b0011
```

```
User: /ed-review approve a3f9c12b0011 --as-answer

Claude: Posted draft a3f9c12b0011 as an answer on thread #312.
  Thread marked as answered. Draft removed from queue.

  2 drafts remaining.
```

```
User: /ed-review reject a3f9c12b0011 --reason "Too much implementation detail"

Claude: Draft a3f9c12b0011 rejected.
  Reason: Too much implementation detail

  2 drafts remaining.
```

---

## Installing the skills

Skills live in `.claude/commands/` in the ed-bot repository. They are automatically discovered by Claude Code when you open the project in your editor.

To verify they are loaded:

```
User: /help

Claude: Available slash commands:
  /ed-status    — Show knowledge base and draft queue status
  /ed-ingest    — Ingest threads, projects, or lectures
  /ed-answer    — Generate a draft answer for a thread
  /ed-review    — Review and act on pending drafts
  ...
```

## Skill configuration

Skills call the `ed` CLI internally, so they respect the same `~/.ed-bot/config.yaml` and environment variables as the command line. Make sure `ED_API_TOKEN` and `ANTHROPIC_API_KEY` are set in your shell before starting Claude Code.
