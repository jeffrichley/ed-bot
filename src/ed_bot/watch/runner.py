"""APScheduler runner with retry/backoff + error escalation."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from ed_bot.watch.config import WatchConfig
from ed_bot.watch.emit import emit

log = logging.getLogger(__name__)


@dataclass
class RetryState:
    """Tracks consecutive poll failures so the 30-minute error threshold
    can be enforced and "recovered" emissions can be triggered after recovery.

    Note: ``next_backoff()`` computes an exponential-backoff value for
    observability and possible future use, but the cron-based scheduler does
    NOT consume it — polls fire on their configured cron schedule regardless
    of failure count. The 30-minute elapsed-time threshold in ``_on_error``
    is the actual error-handling mechanism.
    """
    cap_seconds: int
    failures: int = 0
    first_failure_at: Optional[datetime] = None
    alerted: bool = False

    def next_backoff(self) -> int:
        """Increment failure count and return the suggested backoff seconds
        (60, 120, 240, ... capped at ``cap_seconds``). Currently not consumed
        by the scheduler — see class docstring."""
        self.failures += 1
        backoff = 60 * (2 ** (self.failures - 1))
        return min(backoff, self.cap_seconds)

    def reset(self) -> None:
        self.failures = 0
        self.first_failure_at = None
        self.alerted = False


def _on_error(rs: RetryState, threshold_seconds: int) -> None:
    """Record a failure; emit 'error' once if we've been failing for too long."""
    now = datetime.now(timezone.utc)
    if rs.first_failure_at is None:
        rs.first_failure_at = now
    elapsed = (now - rs.first_failure_at).total_seconds()
    if elapsed >= threshold_seconds and not rs.alerted:
        emit("error", reason="api_unavailable_30m")
        rs.alerted = True


def _on_recovery(rs: RetryState) -> None:
    """Emit 'recovered' if we had previously alerted; always reset state."""
    if rs.alerted:
        emit("recovered")
    rs.reset()


def _poll_with_retry(
    poll_once: Callable[[], None],
    rs: RetryState,
    threshold_seconds: int,
) -> None:
    """Run one poll, swallowing errors and feeding the retry state."""
    try:
        poll_once()
        _on_recovery(rs)
    except Exception as e:  # broad: scheduler must keep running
        log.warning("Poll failed: %s", e)
        _on_error(rs, threshold_seconds=threshold_seconds)


def build_scheduler(
    config: WatchConfig,
    poll_once: Callable[[], None],
    *,
    error_threshold_seconds: int = 1800,
    cap_seconds: int = 600,
) -> BlockingScheduler:
    """Construct a BlockingScheduler with one job per non-off window."""
    scheduler = BlockingScheduler()
    rs = RetryState(cap_seconds=cap_seconds)

    def job():
        _poll_with_retry(poll_once, rs, error_threshold_seconds)

    for w in config.windows:
        if w.interval_seconds is None:
            continue
        minute_spec = f"*/{max(w.interval_seconds // 60, 1)}"
        days_spec = ",".join(w.days)

        # CronTrigger.hour uses inclusive ranges; watch.yaml's end_hour is exclusive.
        if w.start_hour < w.end_hour:
            # Normal window, e.g. 09:00-22:00 -> hour=9-21
            scheduler.add_job(
                job,
                trigger=CronTrigger(
                    day_of_week=days_spec,
                    hour=f"{w.start_hour}-{w.end_hour - 1}",
                    minute=minute_spec,
                ),
            )
        else:
            # Wrap window, e.g. 22:00-09:00 -> two jobs: [22-23] and [0-8]
            scheduler.add_job(
                job,
                trigger=CronTrigger(
                    day_of_week=days_spec,
                    hour=f"{w.start_hour}-23",
                    minute=minute_spec,
                ),
            )
            if w.end_hour > 0:
                scheduler.add_job(
                    job,
                    trigger=CronTrigger(
                        day_of_week=days_spec,
                        hour=f"0-{w.end_hour - 1}",
                        minute=minute_spec,
                    ),
                )
    return scheduler


def run(scheduler: BlockingScheduler) -> None:
    """Block on scheduler.start(). Quits cleanly on Ctrl-C."""
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown(wait=False)
