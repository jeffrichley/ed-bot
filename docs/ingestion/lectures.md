# Lecture Ingestion

`ed ingest lectures` runs the full video pipeline: download from Kaltura, transcribe with `faster-whisper`, and generate indexed markdown with complete provenance.

## Prerequisites

Lecture ingestion requires three external dependencies. Install them with the `lectures` extra:

```bash
uv sync --extra lectures
```

This installs:

- **yt-dlp** — video download via Python API
- **ffmpeg** — audio extraction (must also be on `$PATH`)
- **faster-whisper** — local Whisper transcription, no cloud required

Verify ffmpeg is available:

```bash
ffmpeg -version
```

## Command

```bash
ed ingest lectures [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--course INT` | Kaltura course ID |
| `--force` | Re-ingest lectures that have already been processed |
| `--bot-dir PATH` | Override bot directory (default: `~/.ed-bot`) |

### Examples

Ingest all lectures for a course:

```bash
ed ingest lectures --course 91346
```

Force re-ingestion of all lectures (re-downloads and re-transcribes):

```bash
ed ingest lectures --course 91346 --force
```

## Kaltura video handling

Lecture videos hosted on Kaltura are accessed via embed URLs. The ingester converts each Kaltura embed URL to a direct download URL, then uses the yt-dlp Python API to download the video file.

Downloaded video files are stored in `{data_dir}/lectures/videos/` for on-demand frame extraction. The audio track is extracted to a temporary file for transcription, then discarded.

## Transcription

Audio is transcribed locally using `faster-whisper`. The model runs entirely on your hardware — no cloud service required.

Recommended models by hardware:

| Hardware | Model | Notes |
|----------|-------|-------|
| CPU only | `base` or `small` | Slow but no GPU needed |
| CUDA GPU | `medium` or `large-v3` | Best accuracy |
| Apple Silicon | `medium` with `metal` | Fast on M-series |

### SRT subtitle support

If a Kaltura video already has subtitle/caption files (SRT format), the ingester uses them directly instead of running Whisper — significantly faster and often more accurate for professional course recordings.

When SRT captions are available:

```
Lecture 03: Portfolio Theory — using existing SRT captions
```

When transcription is needed:

```
Lecture 04: CAPM — transcribing with faster-whisper (medium)...
```

## Output format

Each lecture is saved as `{data_dir}/lectures/{slug}.md`:

```
~/.ed-bot/knowledge/lectures/
├── week01-introduction-to-ml4t.md
├── week02-market-mechanics.md
├── week03-portfolio-theory.md
└── ...
```

### Frontmatter

```yaml
---
title: "Week 3: Portfolio Theory and Optimization"
week: 3
lesson_id: "lsn_0003"
slide_id: "sld_0312"
edstem_url: "https://edstem.org/us/courses/12345/lessons/0003/slides/0312"
source: kaltura
kaltura_entry_id: "1_abc123de"
transcription_method: faster-whisper
model: medium
ingested: 2025-09-15T10:00:00+00:00
---
```

### Body

After the frontmatter, the file contains timestamped transcript segments:

```markdown
# Week 3: Portfolio Theory and Optimization

## [00:00:00]

In this lecture we explore how to construct an optimal portfolio
given a set of assets and historical return data.

## [00:02:15]

The Sharpe ratio measures risk-adjusted return. It's defined as the
portfolio return minus the risk-free rate, divided by the portfolio
standard deviation...
```

## Provenance and deep links

Every lecture file carries full provenance:

- **lesson_id** — the Kaltura or LMS lesson identifier
- **slide_id** — the specific slide within a lesson
- **EdStem deep link** — direct URL to the slide in EdStem Lessons

This allows the answer engine to cite specific lectures with clickable links in draft answers:

```
Source: Week 3, slide 12 — https://edstem.org/us/courses/12345/lessons/0003/slides/0312
```

## On-demand frame extraction

Video files retained in `{data_dir}/lectures/videos/` can be used for frame extraction at a specific timestamp. This is useful when generating answers that benefit from a screenshot of a specific slide or diagram.

Frame extraction is performed on demand — the video is not pre-processed into frames during ingestion.

## Skip logic

The ingester tracks which lectures have already been processed. On re-runs, already-ingested lectures are skipped unless `--force` is passed:

```
Lecture 01: Introduction — already ingested, skipping
Lecture 02: Data Sources — already ingested, skipping
Lecture 03: Portfolio Theory — transcribing...
```

State is stored in `~/.ed-bot/state/lectures.json`.

## After ingestion

Run `ed index` to load lecture transcripts into the vector store:

```bash
ed ingest lectures --course 91346
ed index
```

Or contextualize first:

```bash
ed ingest lectures --course 91346
ed contextualize -d lectures
ed index
```

## How lecture context appears in drafts

When the answer engine retrieves relevant context, lecture chunks appear under a dedicated section in the Claude prompt:

```
## Relevant Lecture Content

---
Source: Week 3, slide 12 — https://edstem.org/us/courses/12345/lessons/0003/slides/0312
The Sharpe ratio measures risk-adjusted return. In lecture 3 we showed
that maximizing the Sharpe ratio is equivalent to finding the tangent
portfolio on the efficient frontier...
```

This allows Claude to reference specific lectures by name and week, grounding conceptual answers in the actual course material rather than generic knowledge.
