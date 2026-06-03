"""Per-thread draft cache: reuse while fresh, regenerate when the thread moves,
persist edits."""
import pytest

from ed_bot.cockpit import draft_cache
from ed_bot.cockpit.draft_cache import (
    load_cached, save_cached, update_payload, build_cached_draft_fn,
    build_cached_reply_fn,
)
from ed_bot.cockpit.loop import CockpitLoop
from ed_bot.cockpit.models import DraftPayload, UserCommand

pytestmark = pytest.mark.anyio


def _draft(number=188, body="answer body"):
    return DraftPayload(thread_id=8100000 + number, number=number, question="q",
                        body=body, original_content="student: help",
                        project="Project 1 - Martingale")


FRESH = {"reply_count": 3, "is_answered": False}


# --- pure cache behavior ---

def test_save_then_load_roundtrip(tmp_path):
    save_cached(tmp_path, 99, 188, _draft(body="cached"), FRESH)
    got = load_cached(tmp_path, 99, 188, FRESH)
    assert got is not None and got.body == "cached"


def test_load_missing_returns_none(tmp_path):
    assert load_cached(tmp_path, 99, 188, FRESH) is None


def test_stale_on_new_reply(tmp_path):
    save_cached(tmp_path, 99, 188, _draft(), FRESH)
    # A new reply arrived -> reply_count grew -> cache is stale.
    assert load_cached(tmp_path, 99, 188,
                       {"reply_count": 4, "is_answered": False}) is None


def test_stale_on_answered_change(tmp_path):
    save_cached(tmp_path, 99, 188, _draft(), FRESH)
    assert load_cached(tmp_path, 99, 188,
                       {"reply_count": 3, "is_answered": True}) is None


def test_update_payload_keeps_meta(tmp_path):
    save_cached(tmp_path, 99, 188, _draft(body="v1"), FRESH)
    update_payload(tmp_path, 99, 188, _draft(body="v2 edited"))
    got = load_cached(tmp_path, 99, 188, FRESH)  # still fresh (meta unchanged)
    assert got is not None and got.body == "v2 edited"


def test_update_payload_noop_without_existing(tmp_path):
    update_payload(tmp_path, 99, 188, _draft())  # must not raise / create
    assert load_cached(tmp_path, 99, 188, FRESH) is None


# --- build_cached_draft_fn ---

async def test_cache_miss_calls_inner_then_hit_skips_it(tmp_path):
    calls = []

    async def inner(*, number, cwd, course_id):
        calls.append(number)
        return _draft(number=number, body="fresh from agent")

    async def fetch_meta(course_id, number):
        return FRESH

    fn = build_cached_draft_fn(inner=inner, fetch_meta=fetch_meta,
                               cache_dir=tmp_path)
    first = await fn(number=188, cwd=".", course_id=99)
    second = await fn(number=188, cwd=".", course_id=99)
    assert first.body == "fresh from agent"
    assert second.body == "fresh from agent"
    assert calls == [188]  # inner ran once; second was a cache hit


async def test_stale_meta_regenerates(tmp_path):
    calls = []
    metas = iter([{"reply_count": 3, "is_answered": False},
                  {"reply_count": 4, "is_answered": False}])

    async def inner(*, number, cwd, course_id):
        calls.append(number)
        return _draft(number=number)

    async def fetch_meta(course_id, number):
        return next(metas)

    fn = build_cached_draft_fn(inner=inner, fetch_meta=fetch_meta,
                               cache_dir=tmp_path)
    await fn(number=188, cwd=".", course_id=99)
    await fn(number=188, cwd=".", course_id=99)  # reply_count grew -> regen
    assert calls == [188, 188]


async def test_reply_cache_keeps_a_draft_per_target(tmp_path):
    calls = []

    async def inner(*, number, cwd, course_id, target_comment_id):
        calls.append(target_comment_id)
        return DraftPayload(thread_id=8100188, number=number, question="q",
                            body=f"reply {target_comment_id}", post_kind="reply",
                            target_comment_id=target_comment_id)

    async def fetch_meta(course_id, number):
        return FRESH

    fn = build_cached_reply_fn(inner=inner, fetch_meta=fetch_meta,
                               cache_dir=tmp_path)
    a = await fn(number=188, cwd=".", course_id=99, target_comment_id=10)
    b = await fn(number=188, cwd=".", course_id=99, target_comment_id=20)
    a2 = await fn(number=188, cwd=".", course_id=99, target_comment_id=10)  # hit
    assert a.body == "reply 10" and b.body == "reply 20" and a2.body == "reply 10"
    assert calls == [10, 20]  # both targets drafted once; 10 reused from cache
    # both live in the same per-thread file, independently fresh
    assert load_cached(tmp_path, 99, 188, FRESH, target=10).body == "reply 10"
    assert load_cached(tmp_path, 99, 188, FRESH, target=20).body == "reply 20"


async def test_meta_fetch_failure_drafts_fresh(tmp_path):
    async def inner(*, number, cwd, course_id):
        return _draft(number=number, body="drafted anyway")

    async def fetch_meta(course_id, number):
        raise RuntimeError("network down")

    fn = build_cached_draft_fn(inner=inner, fetch_meta=fetch_meta,
                               cache_dir=tmp_path)
    out = await fn(number=188, cwd=".", course_id=99)
    assert out.body == "drafted anyway"  # did not crash


# --- loop persists edits ---

async def test_loop_persists_manual_edit():
    saved = []
    loop = CockpitLoop(cwd=".", course_id=99, draft_fn=None, emit=lambda e: None,
                       rescan_fn=lambda b, p: [],
                       persist_fn=lambda n, p: saved.append((n, p.body)))
    loop._drafts[(188, None)] = _draft(body="OLD")
    loop.update_draft_body(188, "HAND EDITED")
    assert saved == [(188, "HAND EDITED")]


async def test_loop_persists_chat_edit():
    saved = []

    async def chat_edit_fn(**kw):
        return {"reply": "done", "revised_body": "CHAT EDITED"}

    loop = CockpitLoop(cwd=".", course_id=99, draft_fn=None, emit=lambda e: None,
                       chat_edit_fn=chat_edit_fn, rescan_fn=lambda b, p: [],
                       persist_fn=lambda n, p: saved.append((n, p.body)))
    loop._drafts[(188, None)] = _draft(body="OLD")
    await loop.handle(UserCommand(intent="freeform", thread=188, text="reword"))
    assert saved == [(188, "CHAT EDITED")]
