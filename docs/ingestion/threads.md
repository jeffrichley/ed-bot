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
| `--force` | Re-download all threads, ignoring last-sync timestamp |
| `--json` | Output JSON instead of rich text |
| `--bot-dir PATH` | Override bot directory (default: `~/.ed-bot`) |

### Examples

Ingest the current semester (incremental — only updated threads):

```bash
ed ingest threads --semester fall2025
```

Ingest all configured semesters:

```bash
ed ingest threads --all
```

Force a full re-download of all threads:

```bash
ed ingest threads --all --force
```

Machine-readable output:

```bash
ed ingest threads --semester fall2025 --json
# {"semester": "fall2025", "count": 342}
```

## Incremental sync

The ingester records the timestamp of each run in `~/.ed-bot/state/last-sync.json`:

```json
{
  "fall2025": "2025-10-01T12:00:00+00:00",
  "spring2025": "2025-05-15T08:30:00+00:00"
}
```

On subsequent runs only threads updated since that timestamp are fetched, making routine syncs fast. Pass `--force` to re-download every thread regardless:

```bash
ed ingest threads --all --force
```

## Rich progress bar

During ingestion a live Rich progress bar shows per-semester progress with an ETA:

```
Ingesting fall2025... ━━━━━━━━━━━━━━━━━━━━ 100% 342/342 threads [00:45, 7.6 threads/s]
Ingesting spring2025... ━━━━━━━━━━━━━━━━━━━━ 100% 287/287 threads [00:38, 7.5 threads/s]
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

## EdStem XML conversion

Thread content is stored in EdStem's XML-based rich text format. The ingester uses `ed_api.content.ed_xml_to_markdown` to convert it to clean markdown. If that function is unavailable the raw content is stored as-is.

## After ingestion

After ingesting threads, run `ed index` to update the vector store:

```bash
ed ingest threads --all
ed index
```

Or run contextualization first if you want retrieval-augmented context:

```bash
ed ingest threads --all
ed contextualize -d threads
ed index
```
