"""Shared output helpers for Rich/JSON dual-mode output."""

import json
from rich.console import Console

console = Console()


def output(data, json_mode: bool = False):
    """Output data as JSON or Rich formatted text."""
    if json_mode:
        print(json.dumps(data, indent=2, default=str))
    else:
        if isinstance(data, dict):
            for key, value in data.items():
                console.print(f"  {key}: {value}")
        elif isinstance(data, list):
            for item in data:
                console.print(f"  {item}")
        else:
            console.print(str(data))
