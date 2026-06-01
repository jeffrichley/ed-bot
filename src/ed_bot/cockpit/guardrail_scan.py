"""Advisory scan: does a draft body contain a project's Never-Reveal tokens?

This is NOT enforcement — the human reviews every draft before posting. It only
extracts short, literal, high-signal tokens (numbers, fractions, parenthesized
literals) from the 'Never Reveal' section of a guardrail file and reports which
appear verbatim in a body, so the reviewer's eye is drawn to them faster.
"""
from __future__ import annotations

import re
from pathlib import Path

# Literal tokens worth flagging: fractions like 18/38, and parenthesized
# short literals like "(18/38)" or "(episodes x spins)". We only pull tokens
# that are specific enough to be low-false-positive.
_FRACTION = re.compile(r"\b\d{1,4}/\d{1,4}\b")


def _never_reveal_tokens(guardrail_path: Path) -> list[str]:
    """Pull literal flaggable tokens from the 'Never Reveal' section."""
    try:
        text = Path(guardrail_path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return []
    # Isolate the Never Reveal section (until the next '## ' heading).
    m = re.search(r"##\s*Never Reveal\s*(.+?)(?:\n##\s|\Z)", text,
                  re.IGNORECASE | re.DOTALL)
    section = m.group(1) if m else ""
    tokens: list[str] = []
    tokens += _FRACTION.findall(section)
    return sorted(set(tokens))


def scan_body(body: str, guardrail_path: Path) -> list[str]:
    """Return Never-Reveal tokens that appear verbatim in ``body``.

    Empty list means nothing flagged (clean, or no guardrail file)."""
    warnings: list[str] = []
    for token in _never_reveal_tokens(guardrail_path):
        if token in body:
            warnings.append(f"possible Never-Reveal leak: {token}")
    return warnings
