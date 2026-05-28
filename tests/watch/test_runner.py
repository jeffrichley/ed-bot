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
