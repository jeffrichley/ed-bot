"""Backup CLI command — zip the entire ~/.ed-bot directory."""

import json
import pathlib
import zipfile
from datetime import datetime, timezone

import typer
from rich.console import Console

app = typer.Typer(help="Backup the ed-bot data directory.", rich_markup_mode="rich")
console = Console()
err_console = Console(stderr=True)

DEFAULT_BOT_DIR = "~/.ed-bot"


def _get_bot_dir(bot_dir: str) -> pathlib.Path:
    return pathlib.Path(bot_dir).expanduser()


@app.callback(invoke_without_command=True)
def backup(
    output: str = typer.Option(None, "--output", "-o", help="Output zip path. Default: ~/.ed-bot/backups/<timestamp>.zip"),
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Create a backup of the entire ed-bot data directory."""
    bot_path = _get_bot_dir(bot_dir)
    if not bot_path.exists():
        err_console.print(f"[red]Bot directory not found: {bot_path}[/red]")
        raise typer.Exit(1)

    # Determine output path
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    if output:
        zip_path = pathlib.Path(output).expanduser()
    else:
        backups_dir = bot_path / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        zip_path = backups_dir / f"ed-bot-backup-{timestamp}.zip"

    # Collect all files (exclude the backups directory itself)
    all_files = []
    for f in bot_path.rglob("*"):
        if f.is_file() and "backups" not in f.relative_to(bot_path).parts:
            all_files.append(f)

    if not all_files:
        console.print("[yellow]No files to backup.[/yellow]")
        raise typer.Exit(0)

    # Calculate total size for reporting
    total_bytes = sum(f.stat().st_size for f in all_files)
    total_mb = total_bytes / (1024 * 1024)

    console.print(f"[bold]Backing up {len(all_files)} files ({total_mb:.0f} MB)...[/bold]")

    # Create zip with progress
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn, TimeElapsedColumn
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Creating backup", total=len(all_files))

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for f in all_files:
                rel_path = f.relative_to(bot_path)
                zf.write(f, arcname=str(rel_path))
                progress.advance(task)

    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)

    if json_output:
        typer.echo(json.dumps({
            "path": str(zip_path),
            "files": len(all_files),
            "original_size_mb": round(total_mb, 1),
            "zip_size_mb": round(zip_size_mb, 1),
            "timestamp": timestamp,
        }))
    else:
        console.print(f"\n[green]Backup saved:[/green] {zip_path}")
        console.print(f"  Files: {len(all_files)}")
        console.print(f"  Original: {total_mb:.0f} MB")
        console.print(f"  Compressed: {zip_size_mb:.0f} MB")


@app.command()
def list_backups(
    bot_dir: str = typer.Option(DEFAULT_BOT_DIR, "--bot-dir"),
    json_output: bool = typer.Option(False, "--json"),
):
    """List existing backups."""
    bot_path = _get_bot_dir(bot_dir)
    backups_dir = bot_path / "backups"

    if not backups_dir.exists():
        console.print("[yellow]No backups found.[/yellow]")
        return

    zips = sorted(backups_dir.glob("*.zip"), reverse=True)
    if not zips:
        console.print("[yellow]No backups found.[/yellow]")
        return

    if json_output:
        typer.echo(json.dumps([
            {"path": str(z), "size_mb": round(z.stat().st_size / (1024 * 1024), 1),
             "created": datetime.fromtimestamp(z.stat().st_mtime).isoformat()}
            for z in zips
        ]))
    else:
        from rich.table import Table
        table = Table(title="Backups")
        table.add_column("File")
        table.add_column("Size", justify="right")
        table.add_column("Created")
        for z in zips:
            size_mb = z.stat().st_size / (1024 * 1024)
            created = datetime.fromtimestamp(z.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            table.add_row(z.name, f"{size_mb:.0f} MB", created)
        console.print(table)
