# Canvas Integration

`ed ingest canvas` pulls project requirements, course pages, and announcements from Canvas LMS and converts them to indexed markdown. This is the primary way to get structured course content — policies, setup guides, assignment rubrics, and instructor announcements — into the knowledge base.

## Setting up a Canvas API token

1. Log in to Canvas and go to **Account → Settings**
2. Scroll to **Approved Integrations** and click **+ New Access Token**
3. Set a purpose (e.g. "ed-bot") and an expiry date
4. Copy the token — Canvas will only show it once

Export the token before running any `ed ingest canvas` commands:

```bash
export CANVAS_API_TOKEN=your_token_here
```

Add this to your shell profile (`.bashrc`, `.zshrc`, etc.) to make it permanent.

## Finding your Canvas course ID

The course ID appears in the Canvas URL:

```
https://canvas.gatech.edu/courses/498126
                                  ^^^^^^
                                  course_id
```

Optionally set `canvas_course_id` in `config.yaml` so you don't have to pass it on every command:

```yaml
canvas_course_id: 498126
```

## Command

```bash
ed ingest canvas COURSE_ID [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `COURSE_ID` | Canvas course ID |
| `--list` | Preview available assignments without downloading |
| `--filter TEXT` | Only ingest assignments whose name contains this string (default: `"Project"`) |
| `--bot-dir PATH` | Override bot directory |

## Listing assignments

Use `--list` to preview what is available before committing to a download:

```bash
ed ingest canvas 498126 --list
```

```
Canvas assignments for course 498126:
  [123456] Project 1: DTDP (due 2025-09-07, published)
  [123457] Project 2: Optimize Something (due 2025-09-21, published)
  [123458] Project 3: Assess Learners (due 2025-10-05, published)
  [123459] Project 4: Strategy Learner (due 2025-10-19, published)
  [123460] Project 5: Marketsim (due 2025-11-02, published)
  [123461] Project 6: Indicator Evaluation (due 2025-11-16, published)
  [123462] Final Exam (due 2025-12-07, published)
```

## Ingesting project requirements

Pull assignments matching the default filter (`"Project"`):

```bash
ed ingest canvas 498126
```

Pull all assignments regardless of name:

```bash
ed ingest canvas 498126 --filter ""
```

Pull assignments matching a custom filter:

```bash
ed ingest canvas 498126 --filter "Indicator"
```

Project requirements are saved to `{data_dir}/projects/`:

```
~/.ed-bot/knowledge/projects/
├── project-1-dtdp-requirements.md
├── project-2-optimize-something-requirements.md
├── project-3-assess-learners-requirements.md
└── ...
```

## Canvas pages

In addition to assignments, the ingester pulls Canvas **Pages** — static course content like:

- Course policies and grading rubrics
- Environment setup guides
- Project hints (e.g., Strategy Learner hints)
- Office hours schedules

Pages are saved to `{data_dir}/canvas-pages/`:

```
~/.ed-bot/knowledge/canvas-pages/
├── course-policies.md
├── environment-setup.md
├── strategy-learner-hints.md
├── office-hours.md
└── ...
```

## Canvas announcements

Course announcements are also ingested and stored in `{data_dir}/announcements/`:

```
~/.ed-bot/knowledge/announcements/
├── 2025-08-14-welcome-to-ml4t-fall-2025.md
├── 2025-09-01-project-1-clarification.md
├── 2025-09-20-midterm-review-session.md
└── ...
```

Announcements are useful context for the answer engine — they often contain important clarifications that directly address common student questions.

## HTML to markdown conversion

Canvas stores page and assignment content as HTML. The ingester converts this to clean markdown:

- Headings, bold, italic, and links are preserved
- Code blocks and inline code are converted to markdown fences
- Tables are converted to GFM pipe tables
- Images are replaced with alt-text descriptions
- Embedded iframes (e.g., YouTube videos) are replaced with placeholder links

## Frontmatter format

### Assignment (project requirement)

```yaml
---
project: "Project 2"
type: requirements
source: canvas
canvas_assignment_id: 123457
canvas_course_id: 498126
due_at: 2025-09-21T23:59:00+00:00
ingested: 2025-09-01T10:00:00+00:00
---
```

### Canvas page

```yaml
---
title: "Strategy Learner Hints"
type: canvas-page
source: canvas
canvas_page_id: 789012
canvas_course_id: 498126
updated_at: 2025-09-10T14:30:00+00:00
ingested: 2025-09-11T08:00:00+00:00
---
```

### Announcement

```yaml
---
title: "Project 1 Clarification: Data Range"
type: announcement
source: canvas
canvas_announcement_id: 456789
canvas_course_id: 498126
posted_at: 2025-09-01T09:00:00+00:00
ingested: 2025-09-01T10:00:00+00:00
---
```

## After ingestion

Run `ed index` to load Canvas content into the vector store:

```bash
ed ingest canvas 498126
ed index
```
