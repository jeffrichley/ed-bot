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


def _key(target: Optional[int]) -> str:
    """A thread can hold several drafts; key the OP/top-level answer as 'root'
    and a reply by its target comment id."""
    return "root" if target is None else str(target)


def _is_stale(cached_meta: dict, current_meta: dict) -> bool:
    """A draft is stale when new replies arrived or the answered-state changed."""
    return (cached_meta.get("reply_count") != current_meta.get("reply_count")
            or cached_meta.get("is_answered") != current_meta.get("is_answered"))


def _read(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load_cached(cache_dir: Path, course_id: int, number: int, current_meta: dict,
                target: Optional[int] = None) -> Optional[DraftPayload]:
    """Return the saved draft for this target if present and still fresh."""
    data = _read(_path(cache_dir, course_id, number))
    if data is None or _is_stale(data.get("meta", {}), current_meta):
        return None
    raw = data.get("drafts", {}).get(_key(target))
    if raw is None:
        return None
    try:
        return DraftPayload.model_validate(raw)
    except Exception:  # noqa: BLE001 - a corrupt entry just misses the cache
        return None


def save_cached(cache_dir: Path, course_id: int, number: int,
                payload: DraftPayload, current_meta: dict,
                target: Optional[int] = None) -> None:
    """Save a draft for this target. Drafts for other targets in the same thread
    are kept; if the thread moved (meta changed) the stale set is dropped."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _path(cache_dir, course_id, number)
    data = _read(path)
    if data is None or _is_stale(data.get("meta", {}), current_meta):
        data = {"meta": current_meta, "drafts": {}}
    data["meta"] = current_meta
    data.setdefault("drafts", {})[_key(target)] = payload.model_dump()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def update_payload(cache_dir: Path, course_id: int, number: int,
                   payload: DraftPayload) -> None:
    """Rewrite a cached draft's payload after an edit (keyed by its target),
    keeping the staleness meta and other targets' drafts. No-op when there is no
    existing cache entry."""
    path = _path(cache_dir, course_id, number)
    data = _read(path)
    if data is None:
        return
    data.setdefault("drafts", {})[_key(payload.target_comment_id)] = payload.model_dump()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def build_cached_draft_fn(*, inner: InnerDraftFn, fetch_meta: FetchMeta,
                          cache_dir: Path = DEFAULT_CACHE_DIR) -> InnerDraftFn:
    """Wrap a single-draft function with the cache (stored under 'root')."""
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


def build_cached_reply_fn(*, inner, fetch_meta: FetchMeta,
                          cache_dir: Path = DEFAULT_CACHE_DIR):
    """Wrap a per-comment reply-draft function with the cache, keyed by target.
    Reuses a fresh saved reply; else drafts and saves it. Meta-fetch failure
    drafts fresh without caching."""
    async def reply_fn(*, number: int, cwd: str, course_id: int,
                       target_comment_id: Optional[int]) -> DraftPayload:
        try:
            meta = await fetch_meta(course_id, number)
        except Exception:  # noqa: BLE001 - a failed check must not block drafting
            meta = None
        if meta is not None:
            cached = load_cached(cache_dir, course_id, number, meta,
                                 target=target_comment_id)
            if cached is not None:
                return cached
        payload = await inner(number=number, cwd=cwd, course_id=course_id,
                              target_comment_id=target_comment_id)
        if meta is not None:
            save_cached(cache_dir, course_id, number, payload, meta,
                        target=target_comment_id)
        return payload
    return reply_fn
