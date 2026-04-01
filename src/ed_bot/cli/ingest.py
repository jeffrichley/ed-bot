"""Ingest CLI commands."""

import json
import pathlib
import typer
from rich.console import Console

app = typer.Typer(help="Ingest content into the knowledge base.")
console = Console()

DEFAULT_BOT_DIR = "~/.ed-bot"


def _get_bot_dir(bot_dir: str) -> pathlib.Path:
    return pathlib.Path(bot_dir).expanduser()


@app.command()
def threads(
    course: int = typer.Option(None, "--course", help="Course ID"),
    semester: str = typer.Option(None, "--semester", help="Semester name"),
    all_semesters: bool = typer.Option(False, "--all", help="All configured semesters"),
    force: bool = typer.Option(False, "--force", help="Re-download all threads, ignoring last sync"),
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Ingest threads from EdStem. Only downloads new/updated threads since last sync."""
    from ed_api import EdClient
    from ed_bot.config import BotConfig
    from ed_bot.ingestion.threads import ThreadIngester

    config = BotConfig.load(_get_bot_dir(bot_dir))
    client = EdClient(region=config.region)
    ingester = ThreadIngester(config, client)

    if all_semesters:
        total = 0
        for sem in config.semesters:
            count = ingester.ingest(sem["course_id"], sem["name"], force=force)
            total += count
            if not json_output:
                console.print(f"  {sem['name']}: {count} threads")
        if json_output:
            print(json.dumps({"total": total}))
        else:
            console.print(f"[green]Total: {total} threads ingested.[/green]")
    else:
        cid = course or config.course_id
        sem = semester or (config.semesters[0]["name"] if config.semesters else "default")
        count = ingester.ingest(cid, sem, force=force)
        if json_output:
            print(json.dumps({"semester": sem, "count": count}))
        else:
            console.print(f"[green]Ingested {count} threads for {sem}.[/green]")


@app.command()
def projects(
    path: str = typer.Argument(help="Path to PDF or code directory"),
    name: str = typer.Option(None, "--name", help="Project name"),
    type_: str = typer.Option("auto", "--type", help="auto, requirements, or starter-code"),
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Ingest project materials (PDFs or code)."""
    from ed_bot.config import BotConfig
    from ed_bot.ingestion.projects import ProjectIngester

    config = BotConfig.load(_get_bot_dir(bot_dir))
    ingester = ProjectIngester(config)

    file_path = pathlib.Path(path)
    project_name = name or file_path.stem

    if file_path.suffix.lower() == ".pdf":
        count = ingester.ingest_pdf(file_path, project_name)
    else:
        count = ingester.ingest_code(file_path, project_name)

    if json_output:
        print(json.dumps({"project": project_name, "count": count}))
    else:
        console.print(f"[green]Ingested {count} files for {project_name}.[/green]")
