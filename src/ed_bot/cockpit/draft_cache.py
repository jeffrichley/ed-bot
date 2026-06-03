"""Persist cockpit drafts per thread and reuse them while the thread is
unchanged, so re-opening a thread does not re-run the agent.

A cached draft is reused only when the thread's ``reply_count`` and
``is_answered`` are unchanged since it was generated (the same signal the
watcher trusts). A new reply, or the thread becoming answered, invalidates the
cache and triggers a fresh draft. Manual and chat edits are written back so a
curated draft survives a restart.

One JSON file per thread at ``~/.ed-bot/cockpit-drafts/<course>-<number>.json``:
``{"payload": {...DraftPayload...}, "meta": {"reply_count": N, "is_answered": b}}``
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Awaitable, Callable, Optional

from ed_bot.cockpit.models import DraftPayload

DEFAULT_CACHE_DIR = Path("~/.ed-bot/cockpit-drafts").expanduser()

# (course_id, number) -> {"reply_count": int, "is_answered": bool}
FetchMeta = Callable[[int, int], Awaitable[dict]]
InnerDraftFn = Callable[..., Awaitable[DraftPayload]]


def _path(cache_dir: Path, course_id: int, number: int) -> Path:
    return cache_dir / f"{course_id}-{number}.json"


def _is_stale(cached_meta: dict, current_meta: dict) -> bool:
    """A draft is stale when new replies arrived or the answered-state changed."""
    return (cached_meta.get("reply_count") != current_meta.get("reply_count")
            or cached_meta.get("is_answered") != current_meta.get("is_answered"))


def load_cached(cache_dir: Path, course_id: int, number: int,
                current_meta: dict) -> Optional[DraftPayload]:
    """Return the saved draft if present and still fresh, else None."""
    path = _path(cache_dir, course_id, number)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if _is_stale(data.get("meta", {}), current_meta):
        return None
    try:
        return DraftPayload.model_validate(data.get("payload", {}))
    except Exception:  # noqa: BLE001 - a corrupt entry just misses the cache
        return None


def save_cached(cache_dir: Path, course_id: int, number: int,
                payload: DraftPayload, current_meta: dict) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    _path(cache_dir, course_id, number).write_text(
        json.dumps({"payload": payload.model_dump(), "meta": current_meta},
                   indent=2),
        encoding="utf-8")


def update_payload(cache_dir: Path, course_id: int, number: int,
                   payload: DraftPayload) -> None:
    """Rewrite a cached draft's payload after an edit, keeping its staleness
    meta. No-op when there is no existing cache entry."""
    path = _path(cache_dir, course_id, number)
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    data["payload"] = payload.model_dump()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def build_cached_draft_fn(*, inner: InnerDraftFn, fetch_meta: FetchMeta,
                          cache_dir: Path = DEFAULT_CACHE_DIR) -> InnerDraftFn:
    """Wrap a draft function with the per-thread cache. Reuses a fresh saved
    draft; otherwise runs ``inner`` and saves the result. If the metadata fetch
    fails, drafts fresh without caching (never blocks drafting)."""
    async def draft_fn(*, number: int, cwd: str, course_id: int) -> DraftPayload:
        try:
            meta = await fetch_meta(course_id, number)
        except Exception:  # noqa: BLE001 - a failed check must not block drafting
            meta = None
        if meta is not None:
            cached = load_cached(cache_dir, course_id, number, meta)
            if cached is not None:
                return cached
        payload = await inner(number=number, cwd=cwd, course_id=course_id)
        if meta is not None:
            save_cached(cache_dir, course_id, number, payload, meta)
        return payload
    return draft_fn
