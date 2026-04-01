# Review Queue

`DraftQueue` manages draft answers as JSON files on disk. Each draft captures the full context needed to review, edit, and post the answer.

## Draft data model

```python
@dataclass
class Draft:
    thread_id: int          # EdStem thread ID
    thread_number: int      # human-readable thread number
    thread_title: str       # thread subject line
    thread_status: str      # ThreadStatus value
    question_type: str      # QuestionType value
    project: str | None     # detected project slug
    priority: str           # "high", "medium", or "low"
    content: str            # the draft text
    context_used: list[str] # source files retrieved from KB
    guardrails_applied: str | None  # guardrail slug used
    draft_id: str           # 12-hex-char UUID fragment (auto-generated)
    created: str            # ISO 8601 UTC timestamp (auto-generated)
```

Drafts are stored as JSON files at `{drafts_dir}/{draft_id}.json`.

## DraftQueue API

### add

```python
queue = DraftQueue(config.drafts_dir)
draft_id = queue.add(draft)
```

Writes `{draft_id}.json` and returns the draft ID.

### get

```python
draft = queue.get("a3f9c12b0011")
# Draft | None
```

### list

```python
# All drafts, sorted high → medium → low priority
drafts = queue.list()

# Filter by project
drafts = queue.list(project="project2")

# Filter by status
drafts = queue.list(status="unanswered")

# Filter by question type
drafts = queue.list(question_type="conceptual")
```

Multiple filters can be combined. Results are always sorted by priority.

### remove

```python
queue.remove("a3f9c12b0011")
```

Deletes the JSON file. Used by `approve` and `reject`.

### update

```python
draft.priority = "low"
queue.update(draft)
```

Overwrites the JSON file in-place. Used by `skip` to push a draft to the back of the queue.

## Draft lifecycle

```
ed answer <thread>
    │
    ▼
 [generate]          Draft created with computed priority
    │
    ▼
 [review]            Staff reads draft, checks context_used
    │
    ├─▶ [approve]    Posted to EdStem → draft removed from queue
    │
    ├─▶ [reject]     Draft removed from queue (with optional reason logged)
    │
    └─▶ [skip]       priority set to "low" → draft stays in queue
```

## Example draft JSON

```json
{
  "thread_id": 98765,
  "thread_number": 312,
  "thread_title": "Why does my portfolio optimizer return NaN?",
  "thread_status": "unanswered",
  "question_type": "project_help",
  "project": "project2",
  "priority": "high",
  "content": "Great question! NaN values in portfolio optimization usually...",
  "context_used": [
    "threads/fall2025/0287-sharpe-nan.md",
    "projects/project2-requirements.md"
  ],
  "guardrails_applied": "project2",
  "draft_id": "a3f9c12b0011",
  "created": "2025-10-01T14:23:05.123456+00:00"
}
```

## Queue inspection via CLI

```bash
# Show the next highest-priority draft
ed review

# List all pending drafts
ed review --list

# Filter by project
ed review --list --project project2

# Filter by status
ed review --list --status unanswered

# JSON output for scripting
ed review --list --json
```

## Approving with options

```bash
# Post as a regular comment
ed review approve a3f9c12b0011

# Post as an answer (marks thread answered)
ed review approve a3f9c12b0011 --as-answer

# Endorse an existing student answer instead of posting
ed review approve a3f9c12b0011 --endorse
```
