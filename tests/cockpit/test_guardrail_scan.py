"""Tests for the advisory Never-Reveal guardrail scan."""
import textwrap

from ed_bot.cockpit.guardrail_scan import scan_body


_GUARDRAIL = textwrap.dedent("""
    # Project 1 — Martingale: Guardrails
    ## Never Reveal
    - The correct win probability for American roulette (18/38)
    - The specific NumPy array layout (episodes x spins)
    ## OK to Discuss
    - What Monte Carlo simulation means
""").strip()


def test_scan_flags_literal_18_38(tmp_path):
    gfile = tmp_path / "martingale.md"
    gfile.write_text(_GUARDRAIL, encoding="utf-8")
    body = "Your RNG should win with probability 18/38, not one half."
    warnings = scan_body(body, gfile)
    assert any("18/38" in w for w in warnings)


def test_scan_clean_body_returns_empty(tmp_path):
    gfile = tmp_path / "martingale.md"
    gfile.write_text(_GUARDRAIL, encoding="utf-8")
    body = "Think about how many pockets are on an American wheel."
    assert scan_body(body, gfile) == []


def test_scan_missing_file_returns_empty(tmp_path):
    # No guardrail file -> nothing to scan against, advisory stays silent.
    assert scan_body("anything 18/38", tmp_path / "nope.md") == []
