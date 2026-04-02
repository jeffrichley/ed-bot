---
name: ed-status
description: Quick dashboard showing EdStem forum state — thread counts, knowledge base stats.
---

# EdStem Status Dashboard

Quick overview of the forum and knowledge base. No drafting, no posting.

## Step 1: Get thread counts

```bash
cd E:\workspaces\school\gt\ed
ed-api threads list 91346 --no-pinned --limit 100 --json
```

Count:
- Total threads in results
- Unanswered (`is_answered` is false)
- With replies but no staff answer
- Recently active (updated in last 24 hours)

## Step 2: Knowledge base stats

```bash
ed status --json
```

Show collection chunk counts.

## Step 3: Present dashboard

```
EdStem Dashboard — CS 7646 Spring 2026
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Forum:
  Unanswered:     X threads
  Student-only:   X threads  
  Active today:   X threads

Knowledge Base:
  Threads:   38,837 chunks (5 semesters)
  Projects:  348 chunks
  Lectures:  3,859 chunks
  Pages:     447 chunks

Run /ed-check to scan and draft answers.
```

## Step 4: Offer next action

Ask if the user wants to:
- Run `/ed-check` to scan and draft
- Run `/ed-answer <number>` for a specific thread
- Run `/ed-ingest` to pull new content

## Usage Reporting

After completing work using this skill, report the outcome by calling `grimoire_record_usage` with:
- skill: "ed-status"
- project: "E:\workspaces\school\gt\ed-bot"
- outcome: "success" | "partial" | "failure"
- context: what you were trying to accomplish
- notes: what went well, what didn't, any instructions that were wrong or missing

This feedback improves the skill over time. Always report, even on success.
