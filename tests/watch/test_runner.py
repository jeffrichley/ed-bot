"""Tests for the runner — scheduler, retry/backoff, error escalation."""
import json
from datetime import datetime
from unittest.mock import MagicMock
import pytest
from freezegun import freeze_time
from ed_bot.watch.runner import RetryState, _on_error, _on_recovery


def test_retry_state_doubles_backoff_until_cap():
    rs = RetryState(cap_seconds=300)
    assert rs.next_backoff() == 60
    assert rs.next_backoff() == 120
    assert rs.next_backoff() == 240
    assert rs.next_backoff() == 300  # capped
    assert rs.next_backoff() == 300


def test_retry_state_resets_on_success():
    rs = RetryState(cap_seconds=300)
    rs.next_backoff(); rs.next_backoff()
    rs.reset()
    assert rs.next_backoff() == 60


def test_on_error_emits_after_30_min_threshold(capsys):
    rs = RetryState(cap_seconds=300)
    with freeze_time("2026-05-28T10:00:00Z"):
        _on_error(rs, threshold_seconds=1800)
    assert capsys.readouterr().out == ""  # not yet
    with freeze_time("2026-05-28T10:31:00Z"):
        _on_error(rs, threshold_seconds=1800)
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["kind"] == "error"
    assert payload["reason"] == "api_unavailable_30m"


def test_on_error_does_not_re_emit_until_recovery(capsys):
    rs = RetryState(cap_seconds=300)
    with freeze_time("2026-05-28T10:00:00Z"):
        _on_error(rs, threshold_seconds=1800)
    with freeze_time("2026-05-28T10:31:00Z"):
        _on_error(rs, threshold_seconds=1800)
    capsys.readouterr()
    with freeze_time("2026-05-28T11:00:00Z"):
        _on_error(rs, threshold_seconds=1800)
    assert capsys.readouterr().out == ""  # already alerted


def test_on_recovery_emits_when_we_had_alerted(capsys):
    rs = RetryState(cap_seconds=300)
    with freeze_time("2026-05-28T10:00:00Z"):
        _on_error(rs, threshold_seconds=1800)
    with freeze_time("2026-05-28T10:31:00Z"):
        _on_error(rs, threshold_seconds=1800)
    capsys.readouterr()
    _on_recovery(rs)
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["kind"] == "recovered"
    assert rs.alerted is False


def test_on_recovery_silent_when_no_prior_alert(capsys):
    rs = RetryState(cap_seconds=300)
    _on_recovery(rs)
    assert capsys.readouterr().out == ""


def test_build_scheduler_wrap_window_creates_two_jobs():
    from ed_bot.watch.config import WatchConfig, Window
    from ed_bot.watch.runner import build_scheduler

    cfg = WatchConfig(
        course_id=98559,
        windows=[Window(
            days=["mon"], start_hour=22, start_minute=0,
            end_hour=9, end_minute=0, interval_seconds=1800,
        )],
        sounds={},
    )
    scheduler = build_scheduler(cfg, lambda: None)
    jobs = scheduler.get_jobs()
    assert len(jobs) == 2  # split into [22-23] and [0-8]
    hour_specs = sorted(str(j.trigger.fields[5]) for j in jobs)
    # APScheduler stringifies fields; just confirm both windows present
    assert any("22-23" in s or "22,23" in s for s in hour_specs), hour_specs
    assert any("0-8" in s or "0,1,2,3,4,5,6,7,8" in s for s in hour_specs), hour_specs


def test_build_scheduler_normal_window_creates_one_job():
    from ed_bot.watch.config import WatchConfig, Window
    from ed_bot.watch.runner import build_scheduler

    cfg = WatchConfig(
        course_id=98559,
        windows=[Window(
            days=["mon"], start_hour=9, start_minute=0,
            end_hour=22, end_minute=0, interval_seconds=300,
        )],
        sounds={},
    )
    scheduler = build_scheduler(cfg, lambda: None)
    assert len(scheduler.get_jobs()) == 1
