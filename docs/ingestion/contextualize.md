# Contextualization

`ed contextualize` generates **contextual retrieval** context for every file in the knowledge base. This step runs before indexing and significantly improves the relevance of retrieved chunks when answering student questions.

## What is contextual retrieval?

Standard vector search embeds each chunk in isolation. A chunk like "The Sharpe ratio is defined as..." has no information about which course, assignment, or topic it belongs to. This makes retrieval noisy — especially when many chunks contain similar phrasing.

Contextual retrieval prepends a short, LLM-generated context summary to each chunk before embedding it:

> *This chunk is from the Week 3 lecture on portfolio theory in GT ML4T. It defines the Sharpe ratio and explains its role in mean-variance optimization for Project 2.*

This context travels with the chunk through the vector index, so queries like "Why does my Sharpe ratio return NaN in project 2?" retrieve far more relevant results.

ed-bot uses [Ollama](https://ollama.com/) to generate these summaries locally — no cloud API required.

## Setting up Ollama

1. Install Ollama from [ollama.com](https://ollama.com/)
2. Pull the default model:

```bash
ollama pull llama3.2
```

3. Verify Ollama is running:

```bash
ollama list
# NAME               ID              SIZE    MODIFIED
# llama3.2:latest    a80c4f17acd5    2.0 GB  2 minutes ago
```

Ollama must be running (`ollama serve`) when you run `ed contextualize`.

## Command

```bash
ed contextualize [SUBCOMMAND] [OPTIONS]
```

### ed contextualize (run)

Process all knowledge base files:

```bash
ed contextualize
```

Process specific directories:

```bash
ed contextualize -d threads -d projects
```

Force regeneration of already-processed files:

```bash
ed contextualize --force
```

Use a different Ollama model:

```bash
ed contextualize --model llama3.1
```

Tune concurrency (default: 8):

```bash
ed contextualize -j 16
```

### ed contextualize status

Check how many files have been contextualized:

```bash
ed contextualize status
```

```
Contextualization status:
  threads/fall2025:    342/342  [████████████████████] 100%
  threads/spring2025:  287/287  [████████████████████] 100%
  projects:             11/11   [████████████████████] 100%
  lectures:            210/333  [████████████░░░░░░░░]  63%
  canvas-pages:         22/22   [████████████████████] 100%
  announcements:        21/21   [████████████████████] 100%

Total: 893/1016 files contextualized
```

## Options reference

| Option | Default | Description |
|--------|---------|-------------|
| `-d, --directory TEXT` | all | Process only this subdirectory (repeatable) |
| `--force` | off | Regenerate context even for already-processed files |
| `--model TEXT` | `llama3.2` | Ollama model to use |
| `-j, --concurrency INT` | `8` | Number of concurrent Ollama requests |
| `--bot-dir PATH` | `~/.ed-bot` | Override bot directory |

## Concurrency tuning

`ed contextualize` sends requests to Ollama asynchronously. The default of 8 concurrent workers gives approximately an **8x speedup** over sequential processing.

Tune `-j` based on your hardware:

| Hardware | Recommended `-j` |
|----------|-----------------|
| Laptop (CPU only) | 4 |
| Desktop with GPU | 8–16 |
| Server with multiple GPUs | 16–32 |

Higher concurrency doesn't always help — if Ollama is CPU-bound, additional workers just queue up. Watch GPU/CPU utilization and tune accordingly.

## Resumability

Contextualization is fully resumable. State is tracked per-file in `~/.ed-bot/state/contextualize/`. If the process is interrupted (Ctrl-C, power outage, Ollama crash), re-running the same command resumes from where it stopped:

```bash
ed contextualize    # runs 500/1016 files, then interrupted
ed contextualize    # resumes from file 501
```

Only files without existing context entries are processed. Use `--force` to reprocess everything:

```bash
ed contextualize --force
```

## Processing specific directories

You can contextualize one content type at a time. This is useful when you've ingested new content and only want to process the new files:

```bash
# After ingesting new lectures
ed ingest lectures --course 91346
ed contextualize -d lectures

# After ingesting Canvas content
ed ingest canvas 498126
ed contextualize -d canvas-pages -d announcements -d projects
```

## Full pipeline

The recommended order for a first-time setup or a major refresh:

```bash
# 1. Ingest all content
ed ingest threads --all
ed ingest canvas 498126
ed ingest lectures --course 91346

# 2. Generate context
ed contextualize

# 3. Index into vector store
ed index

# 4. Verify
ed status
ed contextualize status
```

## Checking progress

Use `ed contextualize status` at any time to see how many files have been processed:

```bash
ed contextualize status
```

The status command reads from `~/.ed-bot/state/contextualize/` without making any Ollama calls, so it's safe to run at any time.
