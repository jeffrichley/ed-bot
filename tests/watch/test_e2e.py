"""End-to-end: poll over a recorded fixture pair."""
import json
import pathlib
import pytest
from ed_bot.watch.poll import poll
from ed_bot.watch.state import WatchAlertStore

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def store(tmp_path):
    s = WatchAlertStore(tmp_path / "tracker.db")
    yield s
    s.close()


@pytest.fixture
def sounds(tmp_path):
    return {k: tmp_path / f"{k}.wav" for k in
            ("new_thread", "followup", "escalation", "error")}


def test_initial_poll_emits_new_and_escalation(store, sounds, capsys):
    poll(course_id=98559,
         fetch=lambda _: load_fixture("threads_initial.json"),
         store=store, play=lambda *a, **kw: None, sound_files=sounds)
    out_lines = [l for l in capsys.readouterr().out.strip().split("\n") if l]
    kinds = sorted(json.loads(l)["kind"] for l in out_lines)
    assert kinds == ["escalation", "new_thread"]  # Announcements thread silent


def test_followup_poll_emits_followup_for_thread_with_new_activity(store, sounds, capsys):
    poll(course_id=98559,
         fetch=lambda _: load_fixture("threads_initial.json"),
         store=store, play=lambda *a, **kw: None, sound_files=sounds)
    capsys.readouterr()
    poll(course_id=98559,
         fetch=lambda _: load_fixture("threads_followup.json"),
         store=store, play=lambda *a, **kw: None, sound_files=sounds)
    out_lines = [l for l in capsys.readouterr().out.strip().split("\n") if l]
    assert len(out_lines) == 1
    payload = json.loads(out_lines[0])
    assert payload["kind"] == "followup"
    assert payload["thread_id"] == 1001
