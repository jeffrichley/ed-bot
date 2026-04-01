"""Guardrails CLI commands."""

import json
import os
import pathlib
import subprocess
import typer
from rich.console import Console

app = typer.Typer(help="Manage project guardrails.")
console = Console()

DEFAULT_BOT_DIR = "~/.ed-bot"


def _get_bot_dir(bot_dir: str) -> pathlib.Path:
    return pathlib.Path(bot_dir).expanduser()


@app.command(name="list")
def list_guardrails(
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """List all guardrail files."""
    from ed_bot.config import BotConfig
    from ed_bot.engine.guardrails import GuardrailsManager

    config = BotConfig.load(_get_bot_dir(bot_dir))
    manager = GuardrailsManager(config.guardrails_dir)
    names = manager.list()
    if json_output:
        print(json.dumps(names))
    else:
        for name in names:
            console.print(f"  {name}")


@app.command()
def edit(
    project: str = typer.Argument(help="Project slug"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Edit guardrails in $EDITOR."""
    from ed_bot.config import BotConfig

    config = BotConfig.load(_get_bot_dir(bot_dir))
    path = config.guardrails_dir / f"{project}.md"
    editor = os.environ.get("EDITOR", "notepad" if os.name == "nt" else "vi")
    subprocess.run([editor, str(path)])
