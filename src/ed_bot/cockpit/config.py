"""Resolve cockpit runtime paths and the active course, never hardcoded.

The agent must run from the directory where ``ed-api`` loads its ``.env`` token
(the sibling ``ed`` working dir), and the active course comes from
``~/.ed-bot/config.yaml`` — both resolved here.
"""
from __future__ import annotations

import re
from pathlib import Path

_DEFAULT_CONFIG = Path("~/.ed-bot/config.yaml").expanduser()


def resolve_course_id(config_path: Path = _DEFAULT_CONFIG) -> int:
    """Read the top-level ``course_id:`` from the ed-bot config file."""
    text = Path(config_path).read_text(encoding="utf-8")
    m = re.search(r"^course_id:\s*(\d+)", text, re.MULTILINE)
    if not m:
        raise ValueError(f"no top-level course_id in {config_path}")
    return int(m.group(1))


def ed_working_dir() -> Path:
    """The sibling ``ed`` directory that holds the ``.env`` API token.

    The cockpit lives in the ``ed-bot`` repo; the runnable CLI workspace with
    the token is its sibling ``ed`` directory.
    """
    repo_root = Path(__file__).resolve().parents[3]  # .../ed-bot
    return (repo_root.parent / "ed").resolve()
