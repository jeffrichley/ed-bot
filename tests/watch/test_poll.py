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


def test_poll_re_emits_when_event_at_changes(store, sound_files, capsys):
    t1 = mk_thread(thread_id=42, updated_at="2026-05-28T10:00:00Z")
    fetch = MagicMock(side_effect=[
        [t1],
        [mk_thread(thread_id=42, updated_at="2026-05-28T11:00:00Z")],
    ])
    play = MagicMock()
    poll(course_id=98559, fetch=fetch, store=store, play=play, sound_files=sound_files)
    capsys.readouterr()
    poll(course_id=98559, fetch=fetch, store=store, play=play, sound_files=sound_files)
    second = capsys.readouterr().out
    assert json.loads(second.strip())["kind"] == "new_thread"
    assert play.call_count == 2


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
                   title="Medical Emergency URGENT")
    poll(course_id=98559, fetch=lambda _: [t1], store=store,
         play=lambda *a, **kw: None, sound_files=sound_files)
    capsys.readouterr()

    # Step 2: same thread, updated_at moved, but the fetch reports only
    # staff has been active since our last alert.
    t2 = mk_thread(thread_id=42, updated_at="2026-05-28T11:00:00Z",
                   title="Medical Emergency URGENT")
    t2["has_non_staff_activity_since_alert"] = False
    poll(course_id=98559, fetch=lambda _: [t2], store=store,
         play=lambda *a, **kw: None, sound_files=sound_files)
    assert capsys.readouterr().out == ""  # no re-emit


def test_poll_reemits_when_non_staff_activity_since_alert(store, sound_files, capsys):
    # Step 1: first alert lands.
    t1 = mk_thread(thread_id=42, updated_at="2026-05-28T10:00:00Z",
                   title="Medical Emergency URGENT")
    poll(course_id=98559, fetch=lambda _: [t1], store=store,
         play=lambda *a, **kw: None, sound_files=sound_files)
    capsys.readouterr()

    # Step 2: a student followed up on the emergency thread.
    t2 = mk_thread(thread_id=42, updated_at="2026-05-28T11:00:00Z",
                   title="Medical Emergency URGENT")
    t2["has_non_staff_activity_since_alert"] = True
    poll(course_id=98559, fetch=lambda _: [t2], store=store,
         play=lambda *a, **kw: None, sound_files=sound_files)
    import json
    second = capsys.readouterr().out.strip()
    assert json.loads(second)["kind"] == "escalation"


def test_poll_reemits_when_field_absent_safe_default(store, sound_files, capsys):
    # When the fetch didn't enrich the thread dict (no detail-fetch), default
    # is True (alert).
    t1 = mk_thread(thread_id=42, updated_at="2026-05-28T10:00:00Z")
    poll(course_id=98559, fetch=lambda _: [t1], store=store,
         play=lambda *a, **kw: None, sound_files=sound_files)
    capsys.readouterr()

    t2 = mk_thread(thread_id=42, updated_at="2026-05-28T11:00:00Z")
    # Note: no has_non_staff_activity_since_alert key set
    poll(course_id=98559, fetch=lambda _: [t2], store=store,
         play=lambda *a, **kw: None, sound_files=sound_files)
    assert capsys.readouterr().out != ""
