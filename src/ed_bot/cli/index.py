"""Index CLI command — index all ingested content into pyqmd."""

import json
import typer
from rich.console import Console

app = typer.Typer(help="Index ingested content into the knowledge base.", rich_markup_mode="rich")
console = Console()
err_console = Console(stderr=True)

DEFAULT_BOT_DIR = "~/.ed-bot"


def _get_bot_dir(bot_dir: str):
    import pathlib
    return pathlib.Path(bot_dir).expanduser()


@app.callback(invoke_without_command=True)
def index(
    force: bool = typer.Option(False, "--force", help="Force re-index everything"),
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Index all ingested content into the knowledge base for searching."""
    from ed_bot.config import BotConfig
    from ed_bot.knowledge.collections import KnowledgeBase

    config = BotConfig.load(_get_bot_dir(bot_dir))
    kb = KnowledgeBase(config)

    console.print("[bold]Indexing all content into pyqmd...[/bold]\n")
    results = kb.index_all(force=force)

    if json_output:
        typer.echo(json.dumps(results))
    else:
        from rich.table import Table
        table = Table(title="Indexing Results")
        table.add_column("Collection")
        table.add_column("Chunks Indexed", justify="right")
        total = 0
        for name, count in results.items():
            table.add_row(name, str(count))
            total += count
        table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")
        console.print(table)
