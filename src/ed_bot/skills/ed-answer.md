---
name: ed-answer
description: Generate a draft answer for a specific EdStem thread.
---

Usage: /ed-answer <thread_number>

Run:

```bash
ed answer <thread_number> --json
```

Show the draft to the user. Ask if they want to approve, edit, or regenerate.
If they say approve: `ed approve <draft_id> --json`
