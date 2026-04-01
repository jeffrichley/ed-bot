---
name: ed-review
description: Review draft answers for EdStem forum questions. Present drafts one at a time.
---

1. Get the draft list:

```bash
ed review --list --json
```

2. For each draft, show it to the user with context:

```bash
ed review <draft_id> --json
```

3. Ask the user: approve / edit / reject / skip / regenerate

4. Execute the chosen action:
- approve: `ed approve <draft_id> --json`
- reject: `ed reject <draft_id>`
- skip: `ed skip <draft_id>`
