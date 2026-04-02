"""Contextualize CLI command — generate search context for knowledge base files."""

import json
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Generate search context for knowledge base files via Ollama.")
console = Console()

DEFAULT_BOT_DIR = "~/.ed-bot"


def _get_bot_dir(bot_dir: str):
    import pathlib

    return pathlib.Path(bot_dir).expanduser()


@app.callback(invoke_without_command=True)
def contextualize(
    subdirs: list[str] = typer.Option(None, "--dirs", "-d", help="Subdirectories to process (e.g., -d threads -d projects). Omit for all."),
    model: str = typer.Option("llama3.2", "--model", help="Ollama model to use"),
    concurrency: int = typer.Option(8, "--concurrency", "-j", help="Number of parallel Ollama requests"),
    force: bool = typer.Option(False, "--force", help="Regenerate context even for files that have it"),
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Generate context for all knowledge base files via Ollama. Resumable — safe to stop and restart."""
    import pathlib

    from ed_bot.config import BotConfig
    from ed_bot.contextualize import ContextGenerator

    config = BotConfig.load(_get_bot_dir(bot_dir))
    generator = ContextGenerator(
        knowledge_dir=pathlib.Path(config.data_dir),
        state_dir=config.state_dir,
        model=model,
        concurrency=concurrency,
    )

    results = generator.run(subdirs=subdirs, force=force)

    if json_output:
        print(json.dumps(results))
    else:
        table = Table(title="Context Generation Results")
        table.add_column("Metric")
        table.add_column("Count", justify="right")
        table.add_row("Processed", str(results["processed"]))
        table.add_row("Skipped (already done)", str(results["skipped"]))
        table.add_row("Errors", str(results["errors"]))
        console.print(table)


@app.command()
def status(
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Show context generation progress."""
    import pathlib

    from ed_bot.config import BotConfig
    from ed_bot.contextualize import ContextGenerator

    config = BotConfig.load(_get_bot_dir(bot_dir))
    generator = ContextGenerator(
        knowledge_dir=pathlib.Path(config.data_dir),
        state_dir=config.state_dir,
    )

    info = generator.status()
    if json_output:
        print(json.dumps(info))
    else:
        table = Table(title="Context Generation Status")
        table.add_column("Metric")
        table.add_column("Value")
        for k, v in info.items():
            table.add_row(k, str(v))
        console.print(table)
