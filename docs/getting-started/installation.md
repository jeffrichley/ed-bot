# Installation

ed-bot depends on two sibling packages that live in the same workspace:

- **ed-api** — typed Python client for the EdStem REST API
- **pyqmd** — semantic search over markdown collections

Both are referenced as local editable installs via `uv.sources`.

## Prerequisites

| Tool | Minimum version |
|------|----------------|
| Python | 3.11 |
| [uv](https://docs.astral.sh/uv/) | 0.4+ |
| EdStem API token | — |
| Anthropic API key | — |

## Clone the workspace

ed-bot expects its sibling packages to be present at relative paths. Clone all three repositories into the same parent directory:

```bash
mkdir gt && cd gt
git clone https://github.com/jeffrichley/ed-api
git clone https://github.com/jeffrichley/py-qmd
git clone https://github.com/jeffrichley/ed-bot
```

## Install

```bash
cd ed-bot
uv sync
```

`uv sync` reads `pyproject.toml` and installs ed-api and pyqmd from `../ed-api` and `../py-qmd` as editable packages. All other runtime dependencies (`typer`, `rich`, `pyyaml`, `anthropic`, `markitdown`) are pulled from PyPI.

Verify the install:

```bash
uv run ed --help
```

## Optional: lecture transcription

Lecture ingestion requires `faster-whisper`, which pulls in CUDA/CPU inference libraries and is not installed by default:

```bash
uv sync --extra lectures
```

## Environment variables

Create a `.env` file (or export into your shell) with your API credentials:

```bash
# EdStem API token — generate at https://edstem.org/us/settings/api-tokens
ED_API_TOKEN=your_edstem_token_here

# Anthropic API key — https://console.anthropic.com/
ANTHROPIC_API_KEY=sk-ant-...
```

ed-bot reads `ANTHROPIC_API_KEY` directly via the `anthropic` SDK. The `ed-api` client reads `ED_API_TOKEN` at startup.

!!! warning "Never commit API keys"
    Add `.env` to your `.gitignore`. ed-bot will raise a clear error if a required key is missing.

## Development install

To also run the test suite:

```bash
uv sync --group dev
uv run pytest
```
