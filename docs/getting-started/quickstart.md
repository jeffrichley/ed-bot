# Quick Start

This walkthrough takes you from a fresh install to approving your first AI-drafted answer in under ten minutes.

## 1. Create the bot directory

```bash
mkdir -p ~/.ed-bot/playbook/guardrails
```

## 2. Write config.yaml

```bash
cat > ~/.ed-bot/config.yaml << 'EOF'
course_id: 12345
region: us
semesters:
  - name: fall2025
    course_id: 12345
data_dir: ~/.ed-bot/knowledge
playbook_dir: ~/.ed-bot/playbook
draft_queue_dir: ~/.ed-bot/drafts
EOF
```

Replace `12345` with your actual EdStem course ID.

## 3. Set API credentials

```bash
export ED_API_TOKEN=your_edstem_token
export ANTHROPIC_API_KEY=sk-ant-...
```

## 4. Write a minimal style guide

The style guide is injected into every system prompt. Keep it concise:

```bash
cat > ~/.ed-bot/playbook/style-guide.md << 'EOF'
# GT ML4T TA Style Guide

You are a teaching assistant for Georgia Tech's ML4T course. Your goal is to
help students learn, not to do their work for them.

- Be friendly and encouraging but academically rigorous.
- Never provide complete solution code for graded assignments.
- Use a Socratic approach for conceptual questions.
- Reference specific lectures or documentation when relevant.
- Keep responses concise — students are busy.
EOF
```

## 5. Ingest threads

Pull all forum threads for the current semester:

```bash
ed ingest threads --semester fall2025
```

Expected output:

```
Ingested 342 threads for fall2025.
```

Threads are stored as markdown files under `~/.ed-bot/knowledge/threads/fall2025/`.

## 6. Check status

```bash
ed status
```

```
Course: 12345
┌────────────────────┬────────┐
│ Collection         │ Chunks │
├────────────────────┼────────┤
│ threads-fall2025   │ 1847   │
└────────────────────┴────────┘

Drafts pending: 0
```

## 7. Draft an answer for a specific thread

Find an unanswered thread on EdStem and note its thread ID from the URL (e.g., `edstem.org/us/courses/12345/discussion/98765`):

```bash
ed answer 98765
```

ed-bot will:

1. Fetch the thread from EdStem
2. Classify its status and detect the relevant project
3. Load the matching guardrail file if one exists
4. Search the knowledge base for relevant past Q&A, project materials, and lecture content
5. Call Claude with the style guide, guardrails, and retrieved context
6. Print the draft and save it to the queue

```
Thread #312: Why does my portfolio optimizer return NaN?
Status: unanswered | Project: project2

--- Draft Answer ---

Great question! NaN values in portfolio optimization usually come from one
of a few sources...

Draft saved: a3f9c12b0011
ed approve a3f9c12b0011 | ed reject a3f9c12b0011
```

## 8. Review the draft

```bash
ed review
```

This shows the highest-priority pending draft with full context.

## 9. Approve and post

```bash
ed review approve a3f9c12b0011 --as-answer
```

The comment is posted to EdStem and the draft is removed from the queue.

Or reject if the draft needs improvement:

```bash
ed review reject a3f9c12b0011 --reason "Too much detail on implementation"
```

## Next steps

- Add per-project [guardrails](../engine/guardrails.md) for your assignments
- Ingest [project materials](../ingestion/projects.md) (PDFs and starter code)
- Set up [Claude Code skills](../skills.md) for in-editor review
