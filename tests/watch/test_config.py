"""Tests for watch.config — YAML parsing + validation."""
import pathlib
import pytest
from ed_bot.watch.config import (
    load,
    parse_duration,
    parse_hours,
    ScheduleError,
)


def write_yaml(path: pathlib.Path, body: str) -> pathlib.Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_parse_duration_minutes():
    assert parse_duration("5m") == 300


def test_parse_duration_seconds():
    assert parse_duration("30s") == 30


def test_parse_duration_hours():
    assert parse_duration("2h") == 7200


def test_parse_duration_off():
    assert parse_duration("off") is None


def test_parse_duration_invalid():
    with pytest.raises(ValueError):
        parse_duration("5 minutes")


def test_parse_hours():
    assert parse_hours("09:00-22:00") == (9, 0, 22, 0)


def test_parse_hours_invalid():
    with pytest.raises(ValueError):
        parse_hours("9am to 10pm")


def test_load_minimal_config(tmp_path):
    cfg = write_yaml(tmp_path / "w.yaml", """
schedule:
  - days: [mon]
    hours: "09:00-22:00"
    interval: 5m
sounds:
  new_thread: "{ed_bot}/watch/sounds/new.wav"
""")
    result = load(cfg, ed_bot_dir=pathlib.Path("/fake/ed_bot"))
    assert len(result.windows) == 1
    w = result.windows[0]
    assert w.days == ["mon"]
    assert w.start_hour == 9 and w.end_hour == 22
    assert w.interval_seconds == 300
    assert result.sounds["new_thread"] == pathlib.Path("/fake/ed_bot/watch/sounds/new.wav")


def test_load_off_window(tmp_path):
    cfg = write_yaml(tmp_path / "w.yaml", """
schedule:
  - days: [sat, sun]
    hours: "23:00-08:00"
    interval: "off"
""")
    result = load(cfg, ed_bot_dir=pathlib.Path("/fake"))
    assert result.windows[0].interval_seconds is None


def test_overlapping_windows_raise(tmp_path):
    cfg = write_yaml(tmp_path / "w.yaml", """
schedule:
  - days: [mon]
    hours: "09:00-12:00"
    interval: 5m
  - days: [mon]
    hours: "11:00-15:00"
    interval: 10m
""")
    with pytest.raises(ScheduleError) as exc:
        load(cfg, ed_bot_dir=pathlib.Path("/fake"))
    assert "overlap" in str(exc.value).lower()


def test_window_for_returns_matching_window_or_none(tmp_path):
    from datetime import datetime
    cfg = write_yaml(tmp_path / "w.yaml", """
schedule:
  - days: [mon]
    hours: "09:00-22:00"
    interval: 5m
""")
    result = load(cfg, ed_bot_dir=pathlib.Path("/fake"))
    # Monday 10:00
    assert result.window_for(datetime(2026, 5, 25, 10, 0)) is not None
    # Monday 23:00 (gap → no window → "off")
    assert result.window_for(datetime(2026, 5, 25, 23, 0)) is None
    # Tuesday 10:00 (different day)
    assert result.window_for(datetime(2026, 5, 26, 10, 0)) is None


def test_course_id_optional(tmp_path):
    cfg = write_yaml(tmp_path / "w.yaml", """
course_id: 98559
schedule: []
""")
    assert load(cfg, ed_bot_dir=pathlib.Path("/fake")).course_id == 98559


def test_unknown_day_raises(tmp_path):
    cfg = write_yaml(tmp_path / "w.yaml", """
schedule:
  - days: [funday]
    hours: "09:00-22:00"
    interval: 5m
""")
    with pytest.raises(ScheduleError):
        load(cfg, ed_bot_dir=pathlib.Path("/fake"))
