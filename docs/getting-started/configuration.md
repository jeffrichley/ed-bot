# Configuration

ed-bot is configured through a YAML file in your bot directory. By default this is `~/.ed-bot/config.yaml`. Every CLI command accepts `--bot-dir` to override the location.

## Directory structure

After first run, `~/.ed-bot/` will contain:

```
~/.ed-bot/
├── config.yaml            # main configuration
├── knowledge/             # ingested content (data_dir)
│   ├── threads/           # per-semester thread markdown files
│   │   └── fall2025/
│   │       ├── 0001-why-does-my-code-crash.md
│   │       └── ...
│   ├── projects/          # project requirements + starter code
│   │   ├── project1-requirements.md
│   │   └── project1-analysis.md
│   └── lectures/          # lecture transcripts
│       └── week01-intro.md
├── playbook/              # style guide + guardrails (playbook_dir)
│   ├── style-guide.md     # global response style guide
│   └── guardrails/        # per-project guardrail files
│       ├── project1.md
│       └── project2.md
├── drafts/                # draft queue JSON files (draft_queue_dir)
│   └── a3f9c12b0011.json
├── pyqmd/                 # pyqmd vector index data
└── state/
    └── last-sync.json     # tracks last ingestion timestamps
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

# Where to store ingested markdown files
data_dir: ~/.ed-bot/knowledge

# Where the style guide and guardrail files live
playbook_dir: ~/.ed-bot/playbook

# Where draft JSON files are stored
draft_queue_dir: ~/.ed-bot/drafts
```

## BotConfig properties

`BotConfig.load(bot_dir)` resolves these convenience paths:

| Property | Default path |
|----------|-------------|
| `threads_dir` | `{data_dir}/threads` |
| `projects_dir` | `{data_dir}/projects` |
| `lectures_dir` | `{data_dir}/lectures` |
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
