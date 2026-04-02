"""Shared output helpers for Rich/JSON dual-mode output."""

import json
import typer
from rich.console import Console

console = Console()
err_console = Console(stderr=True)


def output(data, json_mode: bool = False):
    """Output data as JSON or Rich formatted text."""
    if json_mode:
        typer.echo(json.dumps(data, indent=2, default=str))
    else:
        if isinstance(data, dict):
            for key, value in data.items():
                console.print(f"  {key}: {value}")
        elif isinstance(data, list):
            for item in data:
                console.print(f"  {item}")
        else:
            console.print(str(data))
