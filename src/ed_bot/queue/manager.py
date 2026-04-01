"""Draft queue CRUD — JSON files on disk."""

import json
import pathlib
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


@dataclass
class Draft:
    """A draft answer waiting for review."""

    thread_id: int
    thread_number: int
    thread_title: str
    thread_status: str
    question_type: str
    project: str | None
    priority: str
    content: str
    context_used: list[str]
    guardrails_applied: str | None
    draft_id: str = ""
    created: str = ""

    def __post_init__(self):
        if not self.draft_id:
            self.draft_id = uuid.uuid4().hex[:12]
        if not self.created:
            self.created = datetime.now(timezone.utc).isoformat()


class DraftQueue:
    """Manages draft answers as JSON files in a directory."""

    def __init__(self, drafts_dir: pathlib.Path):
        self.drafts_dir = pathlib.Path(drafts_dir)
        self.drafts_dir.mkdir(parents=True, exist_ok=True)

    def add(self, draft: Draft) -> str:
        """Add a draft to the queue. Returns the draft_id."""
        path = self.drafts_dir / f"{draft.draft_id}.json"
        path.write_text(json.dumps(asdict(draft), indent=2))
        return draft.draft_id

    def get(self, draft_id: str) -> Draft | None:
        """Get a draft by ID."""
        path = self.drafts_dir / f"{draft_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return Draft(**data)

    def list(
        self,
        project: str | None = None,
        status: str | None = None,
        question_type: str | None = None,
    ) -> list[Draft]:
        """List all drafts, optionally filtered."""
        drafts = []
        for path in sorted(self.drafts_dir.glob("*.json")):
            data = json.loads(path.read_text())
            draft = Draft(**data)
            if project and draft.project != project:
                continue
            if status and draft.thread_status != status:
                continue
            if question_type and draft.question_type != question_type:
                continue
            drafts.append(draft)

        # Sort by priority (high first)
        priority_order = {"high": 0, "medium": 1, "low": 2}
        drafts.sort(key=lambda d: priority_order.get(d.priority, 3))
        return drafts

    def remove(self, draft_id: str) -> None:
        """Remove a draft from the queue."""
        path = self.drafts_dir / f"{draft_id}.json"
        if path.exists():
            path.unlink()

    def update(self, draft: Draft) -> None:
        """Update an existing draft."""
        path = self.drafts_dir / f"{draft.draft_id}.json"
        path.write_text(json.dumps(asdict(draft), indent=2))
