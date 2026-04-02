"""Ingest CLI commands."""

import json
import pathlib
import typer
from rich.console import Console

app = typer.Typer(help="Ingest content into the knowledge base.", rich_markup_mode="rich")
console = Console()
err_console = Console(stderr=True)

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
            typer.echo(json.dumps({"total": total}))
        else:
            console.print(f"[green]Total: {total} threads ingested.[/green]")
    else:
        cid = course or config.course_id
        sem = semester or (config.semesters[0]["name"] if config.semesters else "default")
        count = ingester.ingest(cid, sem, force=force)
        if json_output:
            typer.echo(json.dumps({"semester": sem, "count": count}))
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
        typer.echo(json.dumps({"project": project_name, "count": count}))
    else:
        console.print(f"[green]Ingested {count} files for {project_name}.[/green]")


@app.command()
def canvas(
    canvas_course_id: int = typer.Argument(help="Canvas course ID (from URL)"),
    filter_prefix: str = typer.Option("Project", "--filter", help="Only ingest assignments starting with this prefix. Use '' for all."),
    list_only: bool = typer.Option(False, "--list", help="List assignments without ingesting"),
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Ingest project requirements from Canvas assignments."""
    from ed_bot.config import BotConfig
    from ed_bot.ingestion.canvas import CanvasIngester

    config = BotConfig.load(_get_bot_dir(bot_dir))
    ingester = CanvasIngester(config)

    if list_only:
        assignments = ingester.list_assignments(canvas_course_id)
        if filter_prefix:
            assignments = [a for a in assignments if a["name"].startswith(filter_prefix)]
        if json_output:
            typer.echo(json.dumps(assignments))
        else:
            from rich.table import Table
            table = Table(title=f"Assignments in Canvas course {canvas_course_id}")
            table.add_column("ID", justify="right")
            table.add_column("Name")
            table.add_column("Points", justify="right")
            table.add_column("Description")
            for a in assignments:
                table.add_row(str(a["id"]), a["name"], str(a["points"]), f"{a['desc_length']} chars")
            console.print(table)
        return

    prefix = filter_prefix if filter_prefix else None
    count = ingester.ingest_assignments(canvas_course_id, filter_prefix=prefix)
    if json_output:
        typer.echo(json.dumps({"count": count}))
    else:
        console.print(f"[green]Ingested {count} assignments from Canvas.[/green]")


@app.command()
def lectures(
    course: int = typer.Option(None, "--course", help="Course ID"),
    lesson: str = typer.Option(None, "--lesson", help="Specific lesson title to ingest"),
    json_output: bool = typer.Option(False, "--json"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
):
    """Ingest lecture videos: download, transcribe, extract screenshots."""
    from ed_api import EdClient
    from ed_bot.config import BotConfig
    from ed_bot.ingestion.lectures import LectureIngester

    config = BotConfig.load(_get_bot_dir(bot_dir))
    client = EdClient(region=config.region)
    ingester = LectureIngester(config)

    cid = course or config.course_id

    # Get all lessons with video slides
    console.print(f"[bold]Fetching lessons for course {cid}...[/bold]")
    try:
        video_slides = client.lessons.video_slides(cid)
    except Exception as e:
        err_console.print(f"[red]Failed to fetch lessons: {e}[/red]")
        err_console.print("[dim]The lessons API may not be available yet.[/dim]")
        raise typer.Exit(1)

    if lesson:
        video_slides = [(l, s) for l, s in video_slides if lesson.lower() in l.title.lower()]

    if not video_slides:
        console.print("No video slides found.")
        raise typer.Exit(0)

    console.print(f"Found {len(video_slides)} video slides.")

    total = 0
    for lesson_obj, slide in video_slides:
        count = ingester.ingest_video(
            video_url=slide.video_url,
            lesson_title=f"{lesson_obj.title} - {slide.title}",
            course_id=cid,
            lesson_id=lesson_obj.id,
            slide_id=slide.id,
            slide_title=slide.title,
            region=config.region,
        )
        total += count

    if json_output:
        typer.echo(json.dumps({"count": total}))
    else:
        console.print(f"[green]Ingested {total} lecture videos.[/green]")
