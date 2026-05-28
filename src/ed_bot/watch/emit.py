"""Emit one JSON line per actionable event to stdout."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Literal

EventKind = Literal["new_thread", "followup", "escalation", "error", "recovered"]


def emit(kind: EventKind, **fields) -> None:
    """Write a single JSON event line to stdout, flushed immediately.

    Used by Claude Code's Monitor tool to surface watcher events as chat
    notifications.
    """
    payload = {"kind": kind, **fields, "ts": datetime.now(timezone.utc).isoformat()}
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()
