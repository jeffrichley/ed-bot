# Typer

## App Setup

Create the main app with Rich markup enabled:

```python
import typer

app = typer.Typer(
    name="myapp",
    help="Description of the CLI tool.",
    rich_markup_mode="rich",  # Enables [bold], [green], etc. in help text
)
```

## Defining Commands

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

## Subcommands and Command Groups

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

## Global Options via Callback

Handle `--verbose`, `--quiet`, and `--version` in a callback so they work for all subcommands:

```python
@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    quiet: bool = typer.Option(False, "--quiet", "-q"),
):
    setup_logging(verbose=verbose, quiet=quiet)
```

## Exit Codes and Termination

Use `typer.Exit(code=N)` for controlled exits, `typer.Abort()` for user cancellations. Never use `sys.exit()`.

```python
if invalid:
    console.print("[red]Error:[/red] Invalid input provided")
    raise typer.Exit(code=1)

if not force:
    confirm = typer.confirm("Are you sure?")
    if not confirm:
        raise typer.Abort()
```

## Command Pattern: Separated Architecture

CLI functions are **thin wrappers**. All business logic lives in a `commands/` subpackage. The CLI layer handles ONLY: argument parsing, logging setup, Rich console output, and exit codes.

### Project Structure

```
myapp/
  __init__.py
  cli.py              # Typer app, commands as thin wrappers
  commands/
    __init__.py
    process.py         # Actual logic for the "process" command
    validate.py        # Actual logic for the "validate" command
```

### CLI Layer (thin wrapper)

```python
# cli.py
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

### Commands Layer (pure logic)

```python
# commands/process.py
class ProcessError(Exception): ...

def run(input_file: str) -> ProcessResult:
    # All real work happens here, no Rich, no Typer
    ...
```

### Rules

- **Commands subpackage must not import Rich or Typer.** It's pure Python logic — raises exceptions for errors, returns data for the CLI layer to format.
- **One command module per CLI command.** `cli.py` imports from `commands.*`, never the reverse.
- **CLI catches domain exceptions and translates them** to Rich output + exit codes.
- **This keeps logic testable** without CLI framework dependencies.

## Best Practices

- **Use `rich_markup_mode="rich"`** on the Typer app for consistency with console output.
- **Support `--quiet` / `--verbose` flags** via callback to configure log level early.
- **Use `--yes` for non-interactive and `--dry-run` for preview** — expected CLI UX patterns.
- **Use `typer.confirm()` over custom input handling** — integrates with abort flow and `--yes` flags.
- **Flat CLIs grow messy** — use `add_typer()` subcommand groups early.
- **CLI functions are thin wrappers.** Parse args, call into `commands.*`, format output, handle exit codes. No business logic.
