---
name: ed-ingest
description: Pull latest threads from EdStem and index into the knowledge base.
---

Run:

```bash
ed ingest threads --all --json
```

Then check status:

```bash
ed status --json
```

Report how many new threads were ingested and current knowledge base state.
