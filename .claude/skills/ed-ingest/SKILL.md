---
name: ed-ingest
description: Pull new threads from EdStem, ingest Canvas content, and re-index the knowledge base.
---

# EdStem Content Ingestion

Pull new content and update the knowledge base.

## Step 1: Ingest new threads

```bash
cd E:\workspaces\school\gt\ed
ed ingest threads --all
```

This is incremental — only downloads threads updated since last sync.

## Step 2: Ingest Canvas updates (optional)

If the user asks for Canvas content or it's the start of a new project cycle:

```bash
ed ingest canvas 498126
```

Canvas course ID 498126 = CS7646 SP26.

## Step 3: Re-index

```bash
ed index
```

This re-indexes only changed files (incremental). Use `ed index --force` for a full rebuild.

## Step 4: Report

Show what was ingested:
- How many new/updated threads per semester
- Whether Canvas content was updated
- New knowledge base chunk counts

## Optional: Contextualize new content

If significant new content was ingested (100+ new threads), suggest running contextualization:

```bash
ed contextualize -d threads
```

Note: this takes ~1 second per file via Ollama. For large batches, it can run in the background.

## Usage Reporting

After completing work using this skill, report the outcome by calling `grimoire_record_usage` with:
- skill: "ed-ingest"
- project: "E:\workspaces\school\gt\ed-bot"
- outcome: "success" | "partial" | "failure"
- context: what you were trying to accomplish
- notes: what went well, what didn't, any instructions that were wrong or missing

This feedback improves the skill over time. Always report, even on success.
