# Configuration

ed-bot is configured through a YAML file in your bot directory. By default this is `~/.ed-bot/config.yaml`. Every CLI command accepts `--bot-dir` to override the location.

## Directory structure

After first run, `~/.ed-bot/` will contain:

```
~/.ed-bot/
├── config.yaml            # main configuration
├── knowledge/             # ingested content (data_dir)
│   ├── threads/           # per-semester thread markdown files
│   │   ├── fall2025/
│   │   │   ├── 0001-why-does-my-code-crash.md
│   │   │   └── ...
│   │   └── spring2025/
│   ├── projects/          # project requirements (Canvas or PDF)
│   │   ├── project1-requirements.md
│   │   └── project2-requirements.md
│   ├── lectures/          # lecture transcripts
│   │   ├── week01-intro.md
│   │   └── ...
│   ├── canvas-pages/      # Canvas LMS pages (policies, guides)
│   │   ├── course-policies.md
│   │   └── ...
│   └── announcements/     # Canvas announcements
│       ├── 2025-08-14-welcome.md
│       └── ...
├── playbook/              # style guide + guardrails (playbook_dir)
│   ├── style-guide.md     # global response style guide
│   └── guardrails/        # per-project guardrail files
│       ├── project1.md
│       └── project2.md
├── drafts/                # draft queue JSON files (draft_queue_dir)
│   └── a3f9c12b0011.json
├── pyqmd/                 # pyqmd vector index data
└── state/
    ├── last-sync.json     # tracks last thread ingestion timestamps
    └── contextualize/     # per-file contextualization state
```

## config.yaml

```yaml
# EdStem course ID (shown in the URL: edstem.org/us/courses/<id>)
course_id: 12345

# EdStem region: "us" or "au"
region: us

# Semesters to manage — used by `ed ingest threads --all`
semesters:
  - name: fall2025
    course_id: 12345
  - name: spring2025
    course_id: 11111

# Canvas LMS course ID (shown in the URL: canvas.institution.edu/courses/<id>)
canvas_course_id: 498126

# Kaltura course ID for lecture video downloads
kaltura_course_id: 91346

# Where to store ingested markdown files
data_dir: ~/.ed-bot/knowledge

# Where the style guide and guardrail files live
playbook_dir: ~/.ed-bot/playbook

# Where draft JSON files are stored
draft_queue_dir: ~/.ed-bot/drafts

# Ollama model used by `ed contextualize` (default: llama3.2)
# contextualize_model: llama3.2
```

## API credentials

ed-bot reads credentials from environment variables. Add these to your shell profile (`.bashrc`, `.zshrc`, etc.):

```bash
# EdStem API token (required for thread ingestion)
export ED_API_TOKEN=your_edstem_token

# Anthropic API key (required for answer generation)
export ANTHROPIC_API_KEY=sk-ant-...

# Canvas API token (required for Canvas ingestion)
export CANVAS_API_TOKEN=your_canvas_token
```

### Obtaining a Canvas API token

1. Log in to Canvas and go to **Account → Settings**
2. Scroll to **Approved Integrations** and click **+ New Access Token**
3. Set a purpose (e.g. "ed-bot") and an expiry date
4. Copy the token — Canvas will not show it again

!!! warning "Token scope"
    The Canvas token only needs read access to your course. Do not grant write permissions unless you intend to post announcements or grades through ed-bot.

## BotConfig properties

`BotConfig.load(bot_dir)` resolves these convenience paths:

| Property | Default path |
|----------|-------------|
| `threads_dir` | `{data_dir}/threads` |
| `projects_dir` | `{data_dir}/projects` |
| `lectures_dir` | `{data_dir}/lectures` |
| `canvas_pages_dir` | `{data_dir}/canvas-pages` |
| `announcements_dir` | `{data_dir}/announcements` |
| `guardrails_dir` | `{playbook_dir}/guardrails` |
| `style_guide_path` | `{playbook_dir}/style-guide.md` |
| `drafts_dir` | `{draft_queue_dir}` |
| `state_dir` | `{bot_dir}/state` |

## Using a custom bot directory

Any command can be pointed at a different config directory with `--bot-dir`:

```bash
ed status --bot-dir ~/my-other-course
ed ingest threads --bot-dir /srv/ed-bot/ml4t
```

This makes it straightforward to manage multiple courses with separate configurations.

## Semester configuration

The `semesters` list drives `ed ingest threads --all`. Each entry needs a human-readable `name` (used as the subdirectory under `threads/`) and the `course_id` for that offering:

```yaml
semesters:
  - name: fall2025
    course_id: 12345
  - name: spring2026
    course_id: 13000
```

Single-semester usage can pass `--course` and `--semester` directly instead:

```bash
ed ingest threads --course 12345 --semester fall2025
```
