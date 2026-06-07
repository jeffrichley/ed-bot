# ed-bot task runner — `just <recipe>`

# Default: list available recipes
default:
    @just --list

# Launch the cockpit TUI (polls the live forum)
tui:
    uv run python -m ed_bot.cockpit

# Cockpit seeded with thread number(s), comma-separated: `just tui-seed 222` or `just tui-seed 222,225`
tui-seed NUMBERS:
    uv run python -m ed_bot.cockpit --seed {{NUMBERS}}

# Cockpit without live polling (seed-only / offline)
tui-no-watch:
    uv run python -m ed_bot.cockpit --no-watch

# Run the test suite
test:
    uv run pytest
