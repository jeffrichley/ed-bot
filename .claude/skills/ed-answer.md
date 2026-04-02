---
name: ed-answer
description: Draft an answer for a specific EdStem thread using the knowledge base, guardrails, and style guide.
---

# EdStem Answer Drafter

Draft an answer for a specific thread. Usage: `/ed-answer <thread_number>`

## Prerequisites

All commands run from `E:\workspaces\school\gt\ed` directory.
- Course ID: 91346 (from `~/.ed-bot/config.yaml`)
- Knowledge base: `~/.ed-bot/pyqmd`

## Step 1: Fetch the thread

```bash
cd E:\workspaces\school\gt\ed
ed-api threads get 91346:<thread_number> --json
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

Present the draft to the user.

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
3. Reference past threads when directly relevant.
4. Be encouraging and patient.
5. When unsure, tell the user you're not confident rather than guessing.
6. Post as `--answer`, not a plain comment.
