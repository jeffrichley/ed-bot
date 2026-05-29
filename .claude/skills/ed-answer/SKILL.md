---
name: ed-answer
description: Draft an answer for a specific EdStem thread using the knowledge base, guardrails, and style guide.
---

# EdStem Answer Drafter

Draft an answer for a specific thread. Usage: `/ed-answer <thread_number>`

## ⛔ MANDATORY PRE-PRESENTATION CHECKLIST

Before any draft is shown to the user, ALL of these must be true:

- [ ] Step 3 guardrails loaded and checked against the draft
- [ ] **Step 5b `/humanizer` skill has been run on the draft.** Not optional. Not skippable when "the draft already sounds fine." Every draft, every time.
- [ ] No solution code, KB references, or rubric criticism

If you find yourself about to present a draft without having explicitly invoked `/humanizer`, STOP and run it first.

## Prerequisites

All commands run from the `E:\workspaces\school\gt\ed` directory (so the
`.env` API token loads).
- **Active course:** resolve at runtime from `~/.ed-bot/config.yaml` (the
  top-level `course_id:` key). NEVER hardcode a course ID — it changes every
  semester.
- Knowledge base: `~/.ed-bot/pyqmd`

## Step 1: Fetch the thread

`ed-api threads get` accepts either a bare thread ID or `course_id:number`.
If you already have the thread ID (e.g. surfaced by `/ed-watch`), pass it
directly. Otherwise resolve the active course from config first:

```powershell
Set-Location E:\workspaces\school\gt\ed
$course = (Select-String -Path $HOME\.ed-bot\config.yaml -Pattern '^course_id:\s*(\d+)').Matches[0].Groups[1].Value
ed-api threads get "${course}:<thread_number>" --json
```

Display the full question and any existing comments to the user.

## Step 2: Search knowledge base

Extract key phrases from the question and search:

```bash
qmd search "<thread title + key concepts>" --data-dir ~/.ed-bot/pyqmd --json --top-k 10
```

Show the user what context was found (top 3-5 results summarized).

## Step 3: Load guardrails

Detect the project from the thread's category. Check for a guardrails file:
```bash
cat ~/.ed-bot/playbook/guardrails/<project-slug>.md
```

If it exists, follow it strictly. If not, apply default caution — never reveal solution code.

## Step 4: Load style guide

```bash
cat ~/.ed-bot/playbook/style-guide.md
```

Classify the question type and apply the matching tone:
- **logistics** → direct, factual
- **setup** → step-by-step instructions
- **conceptual** → Socratic, guiding questions first
- **project_help** → never provide solutions, redirect to concepts
- **teaching_moment** → thorough, use examples and analogies

## Step 5: Draft the answer

Write the answer using:
- The retrieved knowledge base context
- The guardrails (if applicable)
- The style guide tone
- References to course materials where relevant

## Step 5b: Humanize the draft (MANDATORY — no exceptions)

Run the `/humanizer` skill on the draft before presenting it. This is not
optional. Skipping this step is a frequent failure mode — the draft "already
sounds fine" is the exact rationalization to ignore.

The answer should read like a real TA wrote it — conversational, varied
sentence structure, no AI-sounding patterns. Pay special attention to
removing stock openers/closers, formulaic bold-header lists, em-dash
overuse, rule-of-three patterns, and significance inflation.

After `/humanizer` returns its final version, present THAT version to the
user. Not the pre-humanizer draft.

## Step 6: User decision

- **Approves** → Post:
  ```bash
  ed-api comments post <thread_id> --body "<answer>" --answer
  ```
- **Edits** → Revise based on feedback, present again
- **Rejects** → Discard, exit

## Rules

1. NEVER provide solution code for graded assignments.
2. Always check guardrails before drafting.
3. Never reference the knowledge base, past threads, or past semesters in answers. The KB is an internal tool. Just state the answer as if you know it.
4. Never criticize or call rubric/instructions "confusing." Clarify what they mean without undermining them.
5. Be encouraging and patient.
6. When unsure, tell the user you're not confident rather than guessing.
7. Post as `--answer`, not a plain comment.
8. **Never present or post a draft without first running it through `/humanizer`.** No exceptions. The pre-humanizer draft is for your eyes only.

## Usage Reporting

After completing work using this skill, report the outcome by calling `grimoire_record_usage` with:
- skill: "ed-answer"
- project: "E:\workspaces\school\gt\ed-bot"
- outcome: "success" | "partial" | "failure"
- context: what you were trying to accomplish
- notes: what went well, what didn't, any instructions that were wrong or missing

This feedback improves the skill over time. Always report, even on success.
