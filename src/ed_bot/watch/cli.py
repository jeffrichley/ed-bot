"""ed watch CLI commands."""
from __future__ import annotations

import logging
import os
import pathlib
import signal
import sys
from typing import Callable

import typer
from ed_bot.watch import config as wconfig
from ed_bot.watch.poll import poll as run_poll
from ed_bot.watch.runner import build_scheduler, run
from ed_bot.watch.sound import play
from ed_bot.watch.state import WatchAlertStore

log = logging.getLogger(__name__)

app = typer.Typer(name="watch", help="Background EdStem forum watcher.",
                  invoke_without_command=True)

DEFAULT_CONFIG = pathlib.Path("~/.ed-bot/watch.yaml").expanduser()
DEFAULT_DB = pathlib.Path("~/.ed-bot/state/tracker.db").expanduser()
PID_FILE = pathlib.Path("~/.ed-bot/state/watch.pid").expanduser()


def _ed_bot_package_dir() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent  # ed_bot/


def _load(config_path: pathlib.Path):
    return wconfig.load(config_path, ed_bot_dir=_ed_bot_package_dir())


def _build_poll_fn(course_id: int, store: WatchAlertStore, sound_files: dict) -> Callable[[], None]:
    """Returns a no-arg callable suitable for the scheduler.

    Cross-references the existing /ed-check tracker (`threads` table in the
    same DB file as watch_alerts) to populate `our_answer_id` and detect
    follow-ups on our answers. Only does a detail-fetch for threads where
    both (a) we've previously answered and (b) the reply count has grown
    since the last /ed-check scan — keeps API cost bounded.
    """
    from ed_api import EdClient
    import sqlite3
    client = EdClient()

    def _tracker_lookup(conn: sqlite3.Connection, thread_id: int) -> tuple[int | None, int]:
        row = conn.execute(
            "SELECT our_answer_id, reply_count_seen FROM threads WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
        if row is None:
            return None, 0
        return row[0], row[1] or 0

    def _has_student_followup(detail, our_answer_id: int) -> bool:
        """Walk replies and look for a non-staff comment posted after our answer."""
        comments = getattr(detail, "comments", None) or []
        our_answer_time = None
        for c in comments:
            cid = getattr(c, "id", None)
            if cid == our_answer_id:
                our_answer_time = getattr(c, "created_at", None) or getattr(c, "updated_at", None)
                break
        if our_answer_time is None:
            return False
        for c in comments:
            if getattr(c, "id", None) == our_answer_id:
                continue
            is_staff = getattr(c, "user_role", "") in {"admin", "staff", "instructor", "ta"}
            created = getattr(c, "created_at", None) or getattr(c, "updated_at", None)
            if not is_staff and created and created > our_answer_time:
                return True
            # Walk nested replies
            for r in getattr(c, "replies", None) or []:
                r_is_staff = getattr(r, "user_role", "") in {"admin", "staff", "instructor", "ta"}
                r_created = getattr(r, "created_at", None) or getattr(r, "updated_at", None)
                if not r_is_staff and r_created and r_created > our_answer_time:
                    return True
        return False

    def fetch(cid: int) -> list[dict]:
        threads = client.threads.list(cid, limit=100)
        # Open the shared tracker DB (read-only is sufficient).
        tracker_path = pathlib.Path("~/.ed-bot/state/tracker.db").expanduser()
        results = []
        with sqlite3.connect(str(tracker_path)) as conn:
            for t in threads:
                our_answer_id, reply_count_seen = _tracker_lookup(conn, t.id)
                # Cheap heuristic: only detail-fetch when we answered AND replies grew.
                has_followup = False
                if our_answer_id and t.reply_count > reply_count_seen:
                    try:
                        detail = client.threads.get(t.id)
                        has_followup = _has_student_followup(detail, our_answer_id)
                    except Exception as e:
                        log.warning("Followup detail-fetch failed for %d: %s", t.id, e)
                        has_followup = True  # fail open — better to over-alert
                results.append({
                    "thread_id": t.id, "number": t.number, "title": t.title,
                    "category": t.category or "", "is_answered": t.is_answered,
                    "is_pinned": t.is_pinned, "reply_count": t.reply_count,
                    "updated_at": getattr(t, "updated_at", "") or "",
                    "body": "",
                    "our_answer_id": our_answer_id,
                    "has_unanswered_followup": has_followup,
                })
        return results

    def once() -> None:
        run_poll(course_id=course_id, fetch=fetch, store=store,
                 play=play, sound_files=sound_files)

    return once


def _acquire_pid_lock() -> None:
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip() or "0")
        if pid and _pid_alive(pid):
            typer.echo(f"ed watch already running as PID {pid}", err=True)
            raise typer.Exit(code=1)
    PID_FILE.write_text(str(os.getpid()))


def _release_pid_lock() -> None:
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


@app.callback()
def main(
    ctx: typer.Context,
    config_path: pathlib.Path = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
    once: bool = typer.Option(False, "--once", help="Run one poll and exit."),
):
    """Start the watcher (default). Subcommands: status, stop."""
    if ctx.invoked_subcommand is not None:
        return

    cfg = _load(config_path)
    if cfg.course_id is None:
        typer.echo("No course_id in watch.yaml; falling back to ~/.ed-bot/config.yaml not yet wired",
                   err=True)
        raise typer.Exit(code=2)

    store = WatchAlertStore(DEFAULT_DB)
    try:
        poll_fn = _build_poll_fn(cfg.course_id, store, cfg.sounds)

        if once:
            poll_fn()
            return

        _acquire_pid_lock()
        try:
            scheduler = build_scheduler(cfg, poll_fn)
            run(scheduler)
        finally:
            _release_pid_lock()
    finally:
        store.close()


@app.command()
def status():
    """Print whether the watcher is running and its PID."""
    if not PID_FILE.exists():
        typer.echo("ed watch is not running.")
        return
    pid = int(PID_FILE.read_text().strip() or "0")
    if pid and _pid_alive(pid):
        typer.echo(f"ed watch is running as PID {pid}.")
    else:
        typer.echo(f"Stale PID file ({pid}); watcher is not running.")


@app.command()
def stop():
    """Signal the running watcher to shut down."""
    if not PID_FILE.exists():
        typer.echo("ed watch is not running.")
        raise typer.Exit(code=1)
    pid = int(PID_FILE.read_text().strip() or "0")
    if pid and _pid_alive(pid):
        os.kill(pid, signal.SIGTERM)
        # On Windows os.kill(SIGTERM) is TerminateProcess — a hard kill that
        # skips the running watcher's finally cleanup. Clean up the PID file
        # from this side so subsequent `status` doesn't show a stale entry.
        _release_pid_lock()
        typer.echo(f"Sent SIGTERM to PID {pid}.")
    else:
        typer.echo(f"Stale PID file ({pid}); cleaning up.")
        _release_pid_lock()
