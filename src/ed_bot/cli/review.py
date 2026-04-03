"""Review CLI commands."""

import json
import os
import pathlib
import subprocess
import tempfile
import typer
from rich.console import Console

app = typer.Typer(help="Review draft answers.", rich_markup_mode="rich")
console = Console()
err_console = Console(stderr=True)

DEFAULT_BOT_DIR = "~/.ed-bot"


def _get_bot_dir(bot_dir: str) -> pathlib.Path:
    return pathlib.Path(bot_dir).expanduser()


@app.callback(invoke_without_command=True)
def review(
    ctx: typer.Context,
    draft_id: str = typer.Argument(None, help="Draft ID to review"),
    list_all: bool = typer.Option(False, "--list", help="List all drafts"),
    project: str = typer.Option(None, "--project", help="Filter by project"),
    status: str = typer.Option(None, "--status", help="Filter by status"),
    question_type: str = typer.Option(None, "--type", help="Filter by question type"),
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Review drafts. With no args, shows the next highest-priority draft."""
    if ctx.invoked_subcommand is not None:
        return

    from ed_bot.config import BotConfig
    from ed_bot.queue.manager import DraftQueue

    config = BotConfig.load(_get_bot_dir(bot_dir))
    queue = DraftQueue(config.drafts_dir)

    if list_all:
        drafts = queue.list(project=project, status=status, question_type=question_type)
        if json_output:
            typer.echo(json.dumps([
                {"draft_id": d.draft_id, "thread_id": d.thread_id,
                 "thread_number": d.thread_number, "title": d.thread_title,
                 "priority": d.priority, "project": d.project,
                 "question_type": d.question_type, "status": d.thread_status}
                for d in drafts
            ]))
        else:
            for d in drafts:
                console.print(f"  [{d.priority}] {d.draft_id}: #{d.thread_number} {d.thread_title}")
        return

    if draft_id:
        draft = queue.get(draft_id)
    else:
        drafts = queue.list()
        draft = drafts[0] if drafts else None

    if not draft:
        console.print("No drafts to review.")
        return

    if json_output:
        typer.echo(json.dumps({
            "draft_id": draft.draft_id,
            "thread_id": draft.thread_id,
            "thread_number": draft.thread_number,
            "title": draft.thread_title,
            "status": draft.thread_status,
            "question_type": draft.question_type,
            "project": draft.project,
            "priority": draft.priority,
            "content": draft.content,
            "context_used": draft.context_used,
            "guardrails_applied": draft.guardrails_applied,
        }))
    else:
        console.print(f"\n[bold]Draft {draft.draft_id}[/bold]")
        console.print(f"Thread #{draft.thread_number}: {draft.thread_title}")
        console.print(f"Type: {draft.question_type} | Priority: {draft.priority}")
        if draft.project:
            console.print(f"Project: {draft.project}")
        console.print(f"\n[dim]--- Draft Answer ---[/dim]\n")
        console.print(draft.content)
        console.print(
            f"\n[dim]Actions: ed approve {draft.draft_id} | "
            f"ed reject {draft.draft_id} | ed skip {draft.draft_id}[/dim]"
        )


@app.command()
def approve(
    draft_id: str = typer.Argument(help="Draft ID"),
    as_answer: bool = typer.Option(False, "--as-answer", help="Post as answer"),
    endorse: bool = typer.Option(False, "--endorse", help="Endorse instead of posting"),
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Approve and post a draft."""
    from ed_api import EdClient
    from ed_bot.config import BotConfig
    from ed_bot.queue.manager import DraftQueue

    config = BotConfig.load(_get_bot_dir(bot_dir))
    queue = DraftQueue(config.drafts_dir)
    draft = queue.get(draft_id)

    if not draft:
        err_console.print(f"[red]Draft {draft_id} not found.[/red]")
        raise typer.Exit(1)

    client = EdClient(region=config.region)

    if endorse:
        client.threads.endorse(draft.thread_id)
        action = "endorsed"
    else:
        client.comments.post(draft.thread_id, draft.content, is_answer=as_answer)
        action = "posted as answer" if as_answer else "posted"

    queue.remove(draft_id)

    if json_output:
        typer.echo(json.dumps({"status": action, "draft_id": draft_id, "thread_id": draft.thread_id}))
    else:
        console.print(f"[green]Draft {draft_id} {action} on thread {draft.thread_id}.[/green]")


@app.command()
def reject(
    draft_id: str = typer.Argument(help="Draft ID"),
    reason: str = typer.Option(None, "--reason"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Reject a draft."""
    from ed_bot.config import BotConfig
    from ed_bot.queue.manager import DraftQueue

    config = BotConfig.load(_get_bot_dir(bot_dir))
    queue = DraftQueue(config.drafts_dir)
    queue.remove(draft_id)
    console.print(f"Draft {draft_id} rejected.")


@app.command()
def skip(
    draft_id: str = typer.Argument(help="Draft ID"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Skip a draft (move to back of queue)."""
    from ed_bot.config import BotConfig
    from ed_bot.queue.manager import DraftQueue

    config = BotConfig.load(_get_bot_dir(bot_dir))
    queue = DraftQueue(config.drafts_dir)
    draft = queue.get(draft_id)
    if draft:
        draft.priority = "low"
        queue.update(draft)
    console.print(f"Draft {draft_id} skipped.")


@app.command()
def scan(
    limit: int = typer.Option(50, "--limit", help="Number of threads to fetch"),
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Scan for new or updated threads since last check."""
    from ed_api import EdClient
    from ed_bot.config import BotConfig
    from ed_bot.tracker import ThreadTracker

    config = BotConfig.load(_get_bot_dir(bot_dir))
    client = EdClient(region=config.region)
    tracker = ThreadTracker(config.state_dir / "tracker.db")

    api_threads = client.threads.list(config.course_id, limit=limit)

    thread_dicts = [
        {
            "thread_id": t.id,
            "thread_number": t.number,
            "title": t.title,
            "category": t.category,
            "updated_at": t.updated_at.isoformat() if t.updated_at else "",
            "reply_count": t.reply_count,
            "is_answered": t.is_answered,
        }
        for t in api_threads
        if not t.is_pinned
    ]

    changed = tracker.upsert_from_list(thread_dicts)
    tracker.close()

    if json_output:
        typer.echo(json.dumps(changed))
    else:
        if not changed:
            console.print("No new or updated threads.")
        else:
            for t in changed:
                status_icon = {"new": "🆕", "updated": "🔄", "updated_since_answered": "⚠️"}.get(
                    t["tracker_status"], "?"
                )
                console.print(
                    f"  {status_icon} #{t['thread_number']} {t['title']} [{t['tracker_status']}]"
                )
            console.print(f"\n{len(changed)} thread(s) need attention.")
