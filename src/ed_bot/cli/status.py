"""Status CLI command."""

import json
import pathlib
import typer
from rich.console import Console

app = typer.Typer(help="Forum and knowledge base status.", rich_markup_mode="rich")
console = Console()
err_console = Console(stderr=True)

DEFAULT_BOT_DIR = "~/.ed-bot"


def _get_bot_dir(bot_dir: str) -> pathlib.Path:
    return pathlib.Path(bot_dir).expanduser()


@app.callback(invoke_without_command=True)
def status(
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Show forum and knowledge base status."""
    from ed_bot.config import BotConfig
    from ed_bot.knowledge.collections import KnowledgeBase
    from ed_bot.queue.manager import DraftQueue

    config = BotConfig.load(_get_bot_dir(bot_dir))

    kb = KnowledgeBase(config)
    queue = DraftQueue(config.drafts_dir)

    kb_status = kb.status()
    drafts = queue.list()

    if json_output:
        typer.echo(json.dumps({
            "course_id": config.course_id,
            "collections": kb_status,
            "drafts_pending": len(drafts),
        }, default=str))
    else:
        from rich.table import Table
        console.print(f"[bold]Course: {config.course_id}[/bold]")
        table = Table()
        table.add_column("Collection")
        table.add_column("Chunks")
        for name, info in kb_status.items():
            table.add_row(name, str(info.get("chunk_count", 0)))
        console.print(table)
        console.print(f"\nDrafts pending: {len(drafts)}")
