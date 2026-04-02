# Quick Start

This walkthrough takes you from a fresh install to approving your first AI-drafted answer. Follow the steps in order — ingestion, contextualization, and indexing must run before the answer engine has anything to retrieve.

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
canvas_course_id: 498126
data_dir: ~/.ed-bot/knowledge
playbook_dir: ~/.ed-bot/playbook
draft_queue_dir: ~/.ed-bot/drafts
EOF
```

Replace `12345` with your EdStem course ID and `498126` with your Canvas course ID.

## 3. Set API credentials

```bash
export ED_API_TOKEN=your_edstem_token
export ANTHROPIC_API_KEY=sk-ant-...
export CANVAS_API_TOKEN=your_canvas_token
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

## 5. Ingest all content

Run the three ingest commands to pull threads, Canvas content, and lecture transcripts.

### Threads

Pull forum threads for all configured semesters:

```bash
ed ingest threads --all
```

The ingester only downloads threads updated since the last sync. On a first run it fetches everything. A Rich progress bar with ETA shows live status.

```
Ingesting fall2025... ━━━━━━━━━━━━━━━━━━━━ 100% 342/342 threads [00:45]
Ingesting spring2025... ━━━━━━━━━━━━━━━━━━━━ 100% 287/287 threads [00:38]
```

### Canvas

Pull project requirements, course pages, and announcements from Canvas:

```bash
ed ingest canvas 498126
```

To preview what will be ingested before downloading:

```bash
ed ingest canvas 498126 --list
```

### Lectures

Download Kaltura videos, transcribe them, and generate indexed markdown:

```bash
ed ingest lectures --course 91346
```

!!! note "Prerequisites"
    Lecture ingestion requires `yt-dlp`, `ffmpeg`, and `faster-whisper`. Install them with:

    ```bash
    uv sync --extra lectures
    ```

    See [Lecture Ingestion](../ingestion/lectures.md) for details.

## 6. Contextualize

Generate retrieval context for every knowledge base file. This step calls Ollama (llama3.2 by default) to prepend a short context summary to each chunk, which significantly improves retrieval accuracy:

```bash
ed contextualize
```

The process runs with 8 concurrent workers by default and is fully resumable — if it stops, re-run the same command and it picks up where it left off:

```bash
ed contextualize status   # check progress
ed contextualize          # resume if interrupted
```

## 7. Index

Load all contextualized content into the pyqmd vector store:

```bash
ed index
```

This indexes threads (per semester), projects, lectures, Canvas pages, and announcements.

## 8. Check status

```bash
ed status
```

```
Course: 12345
┌────────────────────┬────────┐
│ Collection         │ Chunks │
├────────────────────┼────────┤
│ threads-fall2025   │ 8345   │
│ projects           │  234   │
│ lectures           │  333   │
│ canvas-pages       │   22   │
│ announcements      │   21   │
└────────────────────┴────────┘

Drafts pending: 0
```

## 9. Draft an answer for a specific thread

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

## 10. Review the draft

```bash
ed review
```

This shows the highest-priority pending draft with full context.

## 11. Approve and post

```bash
ed review approve a3f9c12b0011 --as-answer
```

The comment is posted to EdStem and the draft is removed from the queue.

Or reject if the draft needs improvement:

```bash
ed review reject a3f9c12b0011 --reason "Too much detail on implementation"
```

## Keeping the knowledge base current

Run ingest and index again whenever new threads, Canvas content, or lectures are added. Thread ingestion is incremental — only changed threads are re-downloaded:

```bash
ed ingest threads --all
ed ingest canvas 498126
ed index
```

## Next steps

- Add per-project [guardrails](../engine/guardrails.md) for your assignments
- Learn about [Canvas ingestion](../ingestion/canvas.md) (pages, announcements, assignments)
- Tune [contextualization](../ingestion/contextualize.md) concurrency for your hardware
- Set up [Claude Code skills](../skills.md) for in-editor review
