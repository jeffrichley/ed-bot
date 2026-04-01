# Thread Ingestion

`ThreadIngester` pulls threads from the EdStem API and writes each one as a structured markdown file with YAML frontmatter.

## Command

```bash
ed ingest threads [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--semester TEXT` | Semester name (e.g. `fall2025`) |
| `--course INT` | EdStem course ID (overrides config) |
| `--all` | Ingest all semesters defined in config |
| `--json` | Output JSON instead of rich text |
| `--bot-dir PATH` | Override bot directory (default: `~/.ed-bot`) |

### Examples

Ingest the current semester:

```bash
ed ingest threads --semester fall2025
```

Ingest all configured semesters:

```bash
ed ingest threads --all
```

Machine-readable output:

```bash
ed ingest threads --semester fall2025 --json
# {"semester": "fall2025", "count": 342}
```

## Output format

Each thread is saved as `{threads_dir}/{semester}/{number:04d}-{slug}.md`. For example:

```
~/.ed-bot/knowledge/threads/fall2025/0312-why-does-my-portfolio-optimizer-return-nan.md
```

### YAML frontmatter

```yaml
---
thread_id: 98765
thread_number: 312
course_id: 12345
semester: fall2025
category: "Project 2"
subcategory: null
type: question
title: "Why does my portfolio optimizer return NaN?"
author_role: student
status: resolved
is_endorsed: false
is_private: false
created: 2025-09-14T18:32:01+00:00
updated: 2025-09-15T09:10:44+00:00
comment_count: 3
has_staff_response: true
has_accepted_answer: true
---
```

### Body

After the frontmatter, the file contains the thread title as an H1, the original post body converted from EdStem XML to markdown, and each comment labelled by type and author role:

```markdown
# Why does my portfolio optimizer return NaN?

I'm running `optimize_portfolio()` and getting `NaN` for the Sharpe ratio...

## Answer by staff (endorsed)

Great question! NaN values usually come from...

## Comment by student

Thanks! That fixed it.
```

## Incremental sync

The ingester records the time of each run in `~/.ed-bot/state/last-sync.json`:

```json
{
  "fall2025": "2025-10-01T12:00:00+00:00"
}
```

On subsequent runs the same files are overwritten, so the knowledge base always reflects the latest thread state (including new comments and endorsements). Re-index after ingestion to update the vector store:

```bash
ed ingest threads --semester fall2025
# knowledge base is re-indexed automatically on next answer/status call
```

## EdStem XML conversion

Thread content is stored in EdStem's XML-based rich text format. The ingester uses `ed_api.content.ed_xml_to_markdown` to convert it to clean markdown. If that function is unavailable the raw content is stored as-is.

## Knowledge base indexing

Ingested markdown files are indexed into pyqmd's `threads-{semester}` collection on demand. The `KnowledgeBase.index_threads(semester)` method handles collection creation and chunking automatically.
