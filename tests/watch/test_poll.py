"""Tests for poll() — fetch, diff, classify, emit, record."""
import json
import pathlib
from unittest.mock import MagicMock
import pytest
from ed_bot.watch.poll import poll
from ed_bot.watch.state import WatchAlertStore


@pytest.fixture
def store(tmp_path):
    s = WatchAlertStore(tmp_path / "tracker.db")
    yield s
    s.close()


@pytest.fixture
def sound_files(tmp_path):
    return {
        "new_thread": tmp_path / "new.wav",
        "followup": tmp_path / "followup.wav",
        "escalation": tmp_path / "escalation.wav",
        "error": tmp_path / "error.wav",
    }


def mk_thread(**overrides):
    base = {
        "thread_id": 1, "number": 1, "title": "Help with P1",
        "category": "Project 1 | Martingale", "is_answered": False,
        "is_pinned": False, "reply_count": 0,
        "updated_at": "2026-05-28T10:00:00Z",
        "body": "", "our_answer_id": None,
        "has_unanswered_followup": False,
    }
    base.update(overrides)
    return base


def test_poll_emits_for_new_thread(store, sound_files, capsys):
    fetch = MagicMock(return_value=[mk_thread(thread_id=42, number=10)])
    play = MagicMock()
    poll(course_id=98559, fetch=fetch, store=store, play=play, sound_files=sound_files)
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert payload["kind"] == "new_thread"
    assert payload["thread_id"] == 42
    play.assert_called_once_with("new_thread", sound_files)


def test_poll_is_silent_when_no_actionable(store, sound_files, capsys):
    fetch = MagicMock(return_value=[mk_thread(is_pinned=True)])
    play = MagicMock()
    poll(course_id=98559, fetch=fetch, store=store, play=play, sound_files=sound_files)
    assert capsys.readouterr().out == ""
    play.assert_not_called()


def test_poll_records_silent_classifications(store, sound_files):
    t = mk_thread(thread_id=1, is_pinned=True)
    poll(course_id=98559, fetch=lambda _: [t], store=store, play=lambda *a, **kw: None,
         sound_files=sound_files)
    row = store.get(1)
    assert row is not None
    assert row["last_alert_kind"] == "silent"


def test_poll_does_not_re_emit_same_event(store, sound_files, capsys):
    t = mk_thread(thread_id=42, number=10)
    fetch = MagicMock(return_value=[t])
    play = MagicMock()
    poll(course_id=98559, fetch=fetch, store=store, play=play, sound_files=sound_files)
    capsys.readouterr()  # drain
    # Second poll — same thread state.
    poll(course_id=98559, fetch=fetch, store=store, play=play, sound_files=sound_files)
    assert capsys.readouterr().out == ""
    assert play.call_count == 1  # only the first poll


def test_poll_re_emits_when_replies_grow_and_non_staff(store, sound_files, capsys):
    """updated_at change alone is no longer sufficient — reply count must grow."""
    t1 = mk_thread(thread_id=42, updated_at="2026-05-28T10:00:00Z", reply_count=0)
    t2 = mk_thread(thread_id=42, updated_at="2026-05-28T11:00:00Z", reply_count=1)
    t2["has_non_staff_activity_since_alert"] = True
    fetch = MagicMock(side_effect=[[t1], [t2]])
    play = MagicMock()
    poll(course_id=98559, fetch=fetch, store=store, play=play, sound_files=sound_files)
    capsys.readouterr()
    poll(course_id=98559, fetch=fetch, store=store, play=play, sound_files=sound_files)
    second = capsys.readouterr().out
    assert json.loads(second.strip())["kind"] == "new_thread"
    assert play.call_count == 2


def test_poll_silences_reemit_when_reply_count_unchanged(store, sound_files, capsys):
    """Reply count steady = no substantive change, regardless of updated_at."""
    t1 = mk_thread(thread_id=42, updated_at="2026-05-28T10:00:00Z", reply_count=3)
    t2 = mk_thread(thread_id=42, updated_at="2026-05-28T11:00:00Z", reply_count=3)
    fetch = MagicMock(side_effect=[[t1], [t2]])
    play = MagicMock()
    poll(course_id=98559, fetch=fetch, store=store, play=play, sound_files=sound_files)
    capsys.readouterr()
    poll(course_id=98559, fetch=fetch, store=store, play=play, sound_files=sound_files)
    assert capsys.readouterr().out == ""
    assert play.call_count == 1  # only first alert fired


def test_poll_emits_escalation_sound(store, sound_files, capsys):
    t = mk_thread(title="Medical Emergency URGENT")
    fetch = lambda _: [t]
    play = MagicMock()
    poll(course_id=98559, fetch=fetch, store=store, play=play, sound_files=sound_files)
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["kind"] == "escalation"
    play.assert_called_once_with("escalation", sound_files)


def test_poll_includes_url_in_emission(store, sound_files, capsys):
    t = mk_thread(thread_id=42)
    poll(course_id=98559, fetch=lambda _: [t], store=store, play=lambda *a, **kw: None,
         sound_files=sound_files)
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["url"] == "https://edstem.org/us/courses/98559/discussion/42"


def test_poll_silences_reemit_when_only_staff_activity(store, sound_files, capsys):
    # Step 1: first alert lands.
    t1 = mk_thread(thread_id=42, updated_at="2026-05-28T10:00:00Z",
                   title="Medical Emergency URGENT", reply_count=1)
    poll(course_id=98559, fetch=lambda _: [t1], store=store,
         play=lambda *a, **kw: None, sound_files=sound_files)
    capsys.readouterr()

    # Step 2: reply count grew (so the reply-dedup gate opens), but the
    # fetch reports only staff has been active since our last alert.
    t2 = mk_thread(thread_id=42, updated_at="2026-05-28T11:00:00Z",
                   title="Medical Emergency URGENT", reply_count=2)
    t2["has_non_staff_activity_since_alert"] = False
    poll(course_id=98559, fetch=lambda _: [t2], store=store,
         play=lambda *a, **kw: None, sound_files=sound_files)
    assert capsys.readouterr().out == ""  # no re-emit


def test_poll_reemits_when_non_staff_activity_since_alert(store, sound_files, capsys):
    # Step 1: first alert lands.
    t1 = mk_thread(thread_id=42, updated_at="2026-05-28T10:00:00Z",
                   title="Medical Emergency URGENT", reply_count=0)
    poll(course_id=98559, fetch=lambda _: [t1], store=store,
         play=lambda *a, **kw: None, sound_files=sound_files)
    capsys.readouterr()

    # Step 2: a student followed up — reply_count grew AND the activity is
    # from a non-staff user.
    t2 = mk_thread(thread_id=42, updated_at="2026-05-28T11:00:00Z",
                   title="Medical Emergency URGENT", reply_count=1)
    t2["has_non_staff_activity_since_alert"] = True
    poll(course_id=98559, fetch=lambda _: [t2], store=store,
         play=lambda *a, **kw: None, sound_files=sound_files)
    import json
    second = capsys.readouterr().out.strip()
    assert json.loads(second)["kind"] == "escalation"


def test_poll_silent_when_only_updated_at_ticks_no_replies(store, sound_files, capsys):
    """Regression: EdStem ticks updated_at without new replies; we must not
    re-alert. Reply-count dedup short-circuits before the staff filter."""
    t1 = mk_thread(thread_id=42, updated_at="2026-05-28T10:00:00Z", reply_count=0)
    poll(course_id=98559, fetch=lambda _: [t1], store=store,
         play=lambda *a, **kw: None, sound_files=sound_files)
    capsys.readouterr()

    # Same reply_count, different updated_at, no enrichment fields at all.
    t2 = mk_thread(thread_id=42, updated_at="2026-05-28T11:00:00Z", reply_count=0)
    poll(course_id=98559, fetch=lambda _: [t2], store=store,
         play=lambda *a, **kw: None, sound_files=sound_files)
    assert capsys.readouterr().out == ""


def test_poll_dedup_silence_preserves_kind_across_multiple_polls(store, sound_files, capsys):
    """Regression: silencing a re-emit must not overwrite last_alert_kind to
    'silent', or the next poll's guard check (prev_kind == current_kind)
    fails and the thread re-emits."""
    # Poll 1: first alert.
    t1 = mk_thread(thread_id=42, updated_at="2026-05-28T10:00:00Z", reply_count=0)
    poll(course_id=98559, fetch=lambda _: [t1], store=store,
         play=lambda *a, **kw: None, sound_files=sound_files)
    capsys.readouterr()

    # Poll 2: updated_at ticks, no new replies. Should silence.
    t2 = mk_thread(thread_id=42, updated_at="2026-05-28T11:00:00Z", reply_count=0)
    poll(course_id=98559, fetch=lambda _: [t2], store=store,
         play=lambda *a, **kw: None, sound_files=sound_files)
    assert capsys.readouterr().out == ""
    # Row must still report the original kind, not "silent".
    assert store.get(42)["last_alert_kind"] == "new_thread"

    # Poll 3: another updated_at tick, still no new replies. Should also
    # silence — this is the bug we caught: previously kind was wiped to
    # "silent" so this poll's guard didn't match and it re-emitted.
    t3 = mk_thread(thread_id=42, updated_at="2026-05-28T12:00:00Z", reply_count=0)
    poll(course_id=98559, fetch=lambda _: [t3], store=store,
         play=lambda *a, **kw: None, sound_files=sound_files)
    assert capsys.readouterr().out == ""
