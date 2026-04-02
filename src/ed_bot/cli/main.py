"""Typer CLI entry point for ed-bot."""

import logging
import pathlib
import typer
from rich.logging import RichHandler

from ed_bot.cli.ingest import app as ingest_app
from ed_bot.cli.index import app as index_app
from ed_bot.cli.status import app as status_app
from ed_bot.cli.review import app as review_app
from ed_bot.cli.answer import app as answer_app
from ed_bot.cli.guardrails_cmd import app as guardrails_app
from ed_bot.cli.contextualize import app as contextualize_app
from ed_bot.cli.backup import app as backup_app

app = typer.Typer(name="ed", help="EdStem forum automation.", rich_markup_mode="rich")

app.add_typer(ingest_app, name="ingest")
app.add_typer(index_app, name="index", invoke_without_command=True)
app.add_typer(status_app, name="status")
app.add_typer(review_app, name="review")
app.add_typer(answer_app, name="answer")
app.add_typer(guardrails_app, name="guardrails")
app.add_typer(contextualize_app, name="contextualize", invoke_without_command=True)
app.add_typer(backup_app, name="backup", invoke_without_command=True)

DEFAULT_BOT_DIR = "~/.ed-bot"


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    level = logging.DEBUG if verbose else (logging.WARNING if quiet else logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                rich_tracebacks=True,
                tracebacks_show_locals=False,
                show_path=verbose,
                markup=True,
            )
        ],
    )


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug output"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress info output"),
):
    """EdStem forum automation."""
    setup_logging(verbose=verbose, quiet=quiet)


def get_bot_dir(bot_dir: str = DEFAULT_BOT_DIR) -> pathlib.Path:
    return pathlib.Path(bot_dir).expanduser()
