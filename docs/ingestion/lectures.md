# Lecture Ingestion

ed-bot can index lecture transcripts so the answer engine can cite specific course content when answering conceptual questions.

!!! warning "Optional dependency required"
    Lecture transcription uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper), which is **not** installed by default. Install it with the `lectures` extra:

    ```bash
    uv sync --extra lectures
    ```

    Without this extra, you can still manually place transcript markdown files in the lectures directory.

## Lectures directory

Transcript files are stored in `{data_dir}/lectures/`. You can populate this directory manually or via transcription tooling:

```
~/.ed-bot/knowledge/lectures/
├── week01-introduction-to-ml4t.md
├── week02-market-mechanics.md
├── week03-portfolio-theory.md
└── ...
```

## Transcript format

Each lecture file should include YAML frontmatter followed by the transcript body:

```yaml
---
title: "Week 3: Portfolio Theory and Optimization"
week: 3
date: 2025-09-15
topics:
  - mean-variance optimization
  - Sharpe ratio
  - efficient frontier
---

# Week 3: Portfolio Theory and Optimization

## Introduction

In this lecture we explore how to construct an optimal portfolio
given a set of assets and historical return data...

## The Sharpe Ratio

The Sharpe ratio measures risk-adjusted return:

$$S = \frac{R_p - R_f}{\sigma_p}$$

Where $R_p$ is portfolio return, $R_f$ is the risk-free rate,
and $\sigma_p$ is portfolio volatility...
```

## Manual transcript placement

The simplest approach is to use your course recording platform's auto-generated captions, clean them up lightly, and save as markdown:

```bash
# Convert a caption file to a transcript markdown
cp week03-captions.txt ~/.ed-bot/knowledge/lectures/week03-portfolio-theory.md
```

## Using faster-whisper

With the `lectures` extra installed, you can transcribe audio/video files directly. faster-whisper runs entirely locally using Whisper model weights — no cloud service required:

```python
from faster_whisper import WhisperModel

model = WhisperModel("base", device="cpu", compute_type="int8")
segments, info = model.transcribe("lecture03.mp4", beam_size=5)

with open("~/.ed-bot/knowledge/lectures/week03.md", "w") as f:
    f.write("---\ntitle: Week 3\n---\n\n")
    for segment in segments:
        f.write(segment.text + "\n")
```

Recommended models by hardware:

| Hardware | Model | Notes |
|----------|-------|-------|
| CPU only | `base` or `small` | Slow but no GPU needed |
| CUDA GPU | `medium` or `large-v3` | Best accuracy |
| Apple Silicon | `medium` with `metal` | Fast on M-series |

## Knowledge base indexing

Lecture files are indexed into the `lectures` pyqmd collection:

```python
from ed_bot.knowledge.collections import KnowledgeBase
from ed_bot.config import BotConfig

config = BotConfig.load(pathlib.Path("~/.ed-bot").expanduser())
kb = KnowledgeBase(config)
kb.index_lectures()
```

## How lecture context appears in drafts

When the answer engine retrieves relevant context, lecture chunks appear under a dedicated section in the Claude prompt:

```
## Relevant Lecture Content

---
Source: lectures/week03-portfolio-theory.md
The Sharpe ratio measures risk-adjusted return. In lecture 3 we showed
that maximizing the Sharpe ratio is equivalent to finding the tangent
portfolio on the efficient frontier...
```

This allows Claude to reference specific lectures by name and week, grounding conceptual answers in the actual course material rather than generic knowledge.
