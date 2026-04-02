"""Typer CLI entry point for ed-bot."""

import pathlib
import typer

from ed_bot.cli.ingest import app as ingest_app
from ed_bot.cli.index import app as index_app
from ed_bot.cli.status import app as status_app
from ed_bot.cli.review import app as review_app
from ed_bot.cli.answer import app as answer_app
from ed_bot.cli.guardrails_cmd import app as guardrails_app
from ed_bot.cli.contextualize import app as contextualize_app

app = typer.Typer(name="ed", help="EdStem forum automation.")

app.add_typer(ingest_app, name="ingest")
app.add_typer(index_app, name="index", invoke_without_command=True)
app.add_typer(status_app, name="status")
app.add_typer(review_app, name="review")
app.add_typer(answer_app, name="answer")
app.add_typer(guardrails_app, name="guardrails")
app.add_typer(contextualize_app, name="contextualize", invoke_without_command=True)

DEFAULT_BOT_DIR = "~/.ed-bot"


def get_bot_dir(bot_dir: str = DEFAULT_BOT_DIR) -> pathlib.Path:
    return pathlib.Path(bot_dir).expanduser()
