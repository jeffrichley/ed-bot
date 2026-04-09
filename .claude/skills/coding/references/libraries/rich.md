# Rich

## Console Setup

Create console instances for stdout and stderr:

```python
from rich.console import Console

console = Console()
err_console = Console(stderr=True, style="bold red")
```

## Logging with RichHandler

Configure Python logging to use Rich for formatted output:

```python
import logging
from rich.logging import RichHandler

def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                rich_tracebacks=True,
                tracebacks_show_locals=False,  # Keep False to avoid leaking secrets
                show_path=verbose,
                markup=True,
            )
        ],
    )
```

## Output Patterns

Status spinners for long operations:

```python
with console.status("Processing..."):
    result = do_work()
```

Styled output:

```python
console.print("[green]Success:[/green] Operation completed")
console.print("[yellow]Warning:[/yellow] File already exists")
err_console.print("[red]Error:[/red] Failed to connect")
```

Panels for structured output:

```python
from rich.panel import Panel

console.print(Panel(result_text, title="Results", border_style="green"))
```

Tables:

```python
from rich.table import Table

table = Table(title="Results")
table.add_column("Name", style="bold")
table.add_column("Status")
table.add_column("Count", justify="right")

for row in data:
    table.add_row(row.name, row.status, str(row.count))

console.print(table)
```

## Best Practices

- **Lazy-import Rich in CLI commands** — Rich accounts for >85% of Typer startup time. Import inside command functions, not at module top level.
- **Send errors to stderr** — use `Console(stderr=True)` for error output. Keeps stdout clean for piping.
- **Keep `tracebacks_show_locals=False` by default** — prevents accidental exposure of secrets in error output. Only enable in explicit debug modes.
- **Use `console.status()` for operations > 1 second** — gives users feedback that the tool isn't frozen.
- **Use Rich panels for multi-line structured output.** For single-line status, use `console.print()` with markup. For tables or complex results, use `Table` or `Panel`.
- **Always use `RichHandler` for logging.** Never use `print()` for status/debug output.
