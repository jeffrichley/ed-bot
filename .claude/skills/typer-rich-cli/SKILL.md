---
name: typer-rich-cli
description: Build Typer CLI apps with Rich logging, separated command architecture (thin CLI layer + commands subpackage for logic)
source_library: /fastapi/typer, /textualize/rich
generated: 2026-04-02T12:00:00Z
topics:
  - Typer app structure and commands
  - Rich console and logging setup
  - Error handling and exit codes
  - Separation of concerns (CLI vs commands subpackage)
---

# Typer + Rich: CLI Application Pattern

## Reference

### Typer App Setup

Create the main app with Rich markup enabled:

```python
import typer

app = typer.Typer(
    name="myapp",
    help="Description of the CLI tool.",
    rich_markup_mode="rich",  # Enables [bold], [green], etc. in help text
)
```

### Defining Commands

Commands are decorated functions. Use `typer.Argument` for positional args and `typer.Option` for flags:

```python
@app.command()
def process(
    input_file: str = typer.Argument(..., help="Path to input file"),
    output: str = typer.Option("out.json", "--output", "-o", help="Output path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompts"),
):
    """Process the input file and write results."""
    ...
```

### Subcommands and Command Groups

Use separate `typer.Typer()` instances for command groups, then register with `add_typer`:

```python
app = typer.Typer()
db_app = typer.Typer()
cache_app = typer.Typer()

@db_app.command("migrate")
def db_migrate(revision: str = "head"):
    """Run database migrations."""
    ...

@cache_app.command("clear")
def cache_clear():
    """Clear application cache."""
    ...

app.add_typer(db_app, name="db", help="Database operations")
app.add_typer(cache_app, name="cache", help="Cache management")
```

### Exit Codes and Termination

Use `typer.Exit(code=N)` for controlled exits, `typer.Abort()` for user cancellations:

```python
if invalid:
    console.print("[red]Error:[/red] Invalid input provided")
    raise typer.Exit(code=1)

if not force:
    confirm = typer.confirm("Are you sure?")
    if not confirm:
        raise typer.Abort()
```

### Rich Console Setup

Create console instances for stdout and stderr:

```python
from rich.console import Console

console = Console()
err_console = Console(stderr=True, style="bold red")
```

### Rich Logging with RichHandler

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

### Rich Output Patterns

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

## Best Practices

- **Lazy-import Rich in CLI commands** -- Rich accounts for >85% of Typer startup time. Import Rich modules inside command functions, not at module top level, to keep `--help` fast.
- **Use `rich_markup_mode="rich"`** on the Typer app to enable Rich markup in help strings. Prefer this over Markdown mode for consistency with console output.
- **Support `--quiet` / `--verbose` flags** -- Use a callback to configure log level early. `--quiet` suppresses info, `--verbose` enables debug + path display.
- **Use `--yes` for non-interactive and `--dry-run` for preview** -- These are expected UX patterns for CLI tools. Respect them consistently across all commands.
- **Keep `tracebacks_show_locals=False` by default** -- Prevents accidental exposure of secrets, passwords, or tokens in error output. Only enable in explicit debug modes.
- **Use `console.status()` for operations > 1 second** -- Gives users feedback that the tool isn't frozen. Use a descriptive message.
- **Send errors to stderr** -- Create a separate `Console(stderr=True)` for error output. This keeps stdout clean for piping.
- **Flat CLIs grow messy** -- Use `add_typer()` subcommand groups early. Restructuring later is painful.
- **Configure logging once near the entry point** -- Set up handlers, formatters, and levels in the CLI callback or `__main__` block, never inside business logic.

## Instructions

- **Separate CLI from logic.** The CLI layer (`cli.py` or `app.py`) handles ONLY: argument parsing, logging setup, Rich console output, and exit codes. All actual business logic lives in a `commands/` subpackage. CLI functions call into `commands` and format the results.

- **Project structure must follow this layout:**
  ```
  myapp/
    __init__.py
    cli.py              # Typer app, commands as thin wrappers
    commands/
      __init__.py
      process.py        # Actual logic for the "process" command
      validate.py       # Actual logic for the "validate" command
  ```

- **CLI functions are thin wrappers.** A CLI command function should: (1) set up logging, (2) call into `commands.*`, (3) format output with Rich, (4) handle exit codes. It should NOT contain business logic, data transformation, or I/O beyond what Typer/Rich need.

  ```python
  # cli.py -- thin wrapper
  @app.command()
  def process(input_file: str = typer.Argument(...)):
      setup_logging()
      try:
          result = commands.process.run(input_file)
          console.print(f"[green]Done:[/green] {result.summary}")
      except commands.process.ProcessError as e:
          err_console.print(f"[red]Error:[/red] {e}")
          raise typer.Exit(code=1)
  ```

  ```python
  # commands/process.py -- actual logic
  class ProcessError(Exception): ...

  def run(input_file: str) -> ProcessResult:
      # All real work happens here, no Rich, no Typer
      ...
  ```

- **Commands subpackage must not import Rich or Typer.** The `commands/` package is pure Python logic. It raises exceptions for error conditions; the CLI layer catches them and translates to Rich output + exit codes. This keeps the logic testable without CLI dependencies.

- **Always use `RichHandler` for logging.** Never use `print()` for status/debug output. Use `logging.info()`, `logging.debug()`, etc. so output respects `--quiet`/`--verbose`. Reserve `console.print()` for final user-facing results and Rich-formatted output only.

- **Set up logging in a shared function.** Define `setup_logging(verbose: bool = False)` and call it from the Typer callback or from each command. Do not configure logging inside `commands/`.

- **Use a Typer callback for global options.** Handle `--verbose`, `--quiet`, and `--version` in a callback so they work for all subcommands:

  ```python
  @app.callback()
  def main(
      verbose: bool = typer.Option(False, "--verbose", "-v"),
      quiet: bool = typer.Option(False, "--quiet", "-q"),
  ):
      setup_logging(verbose=verbose, quiet=quiet)
  ```

- **Raise `typer.Exit(code=1)` for errors, `typer.Abort()` for user cancellations.** Never use `sys.exit()`. Always print an error message to stderr before exiting with a non-zero code.

- **Use Rich panels for multi-line structured output.** For single-line status, use `console.print()` with markup. For tables or complex results, use `rich.table.Table` or `rich.panel.Panel`.

- **Prefer `typer.confirm()` over custom input handling.** It integrates with Typer's abort flow and respects `--yes` flags when paired with a `--force` or `--yes` option.

## Usage Reporting

After completing work using this skill, report the outcome by calling `grimoire_record_usage` with:
- skill: "typer-rich-cli"
- project: "E:\workspaces\school\gt\ed-bot"
- outcome: "success" | "partial" | "failure"
- context: what you were trying to accomplish
- notes: what went well, what didn't, any instructions that were wrong or missing

This feedback improves the skill over time. Always report, even on success.
