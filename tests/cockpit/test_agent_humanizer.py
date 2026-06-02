"""The drafting agent points at the humanizer skill via progressive disclosure.

The humanizer is a user-level Claude Code skill that the agent's
setting_sources (["project"]) does not load. Instead of injecting its full
~28k-char rule list into every draft, the agent is told to READ the rules file
only when it writes an actual answer, and is granted Read access to that file's
directory via add_dirs.
"""
from pathlib import Path

import pytest

from ed_bot.cockpit import agent
from ed_bot.cockpit.agent import build_options
from ed_bot.cockpit.models import DraftPayload

pytestmark = pytest.mark.anyio


def test_humanizer_directive_points_at_skill_when_present(monkeypatch, tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text("# rules", encoding="utf-8")
    monkeypatch.setattr(agent, "_HUMANIZER_SKILL_PATH", skill)
    directive = agent._humanizer_directive()
    assert str(skill) in directive
    # It must scope humanizing to actual answers, not NEEDS HUMAN flags.
    assert "NEEDS HUMAN" in directive


def test_humanizer_directive_empty_when_skill_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(agent, "_HUMANIZER_SKILL_PATH", tmp_path / "nope.md")
    assert agent._humanizer_directive() == ""


def test_add_dirs_includes_humanizer_dir_when_present(monkeypatch, tmp_path):
    skill = tmp_path / "humanizer" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text("# rules", encoding="utf-8")
    monkeypatch.setattr(agent, "_HUMANIZER_SKILL_PATH", skill)
    dirs = agent._agent_add_dirs()
    assert str(skill.parent) in dirs
    assert agent._ED_BOT_DIR in dirs


def test_add_dirs_omits_humanizer_dir_when_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(agent, "_HUMANIZER_SKILL_PATH", tmp_path / "nope.md")
    dirs = agent._agent_add_dirs()
    assert all("humanizer" not in d for d in dirs)


async def test_draft_thread_appends_humanizer_directive(monkeypatch, tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text("# rules", encoding="utf-8")
    monkeypatch.setattr(agent, "_HUMANIZER_SKILL_PATH", skill)
    captured = {}

    async def fake_sdk_query(*, prompt, schema, cwd):
        captured["prompt"] = prompt
        return DraftPayload(thread_id=1, number=1, question="q", body="b").model_dump()

    await agent.draft_thread(number=1, cwd=".", course_id=99,
                             sdk_query=fake_sdk_query,
                             guardrail_scan=lambda body, path: [])
    assert str(skill) in captured["prompt"]


async def test_draft_thread_no_directive_when_skill_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(agent, "_HUMANIZER_SKILL_PATH", tmp_path / "nope.md")
    captured = {}

    async def fake_sdk_query(*, prompt, schema, cwd):
        captured["prompt"] = prompt
        return DraftPayload(thread_id=1, number=1, question="q", body="b").model_dump()

    await agent.draft_thread(number=1, cwd=".", course_id=99,
                             sdk_query=fake_sdk_query,
                             guardrail_scan=lambda body, path: [])
    assert "human-writing rules" not in captured["prompt"]
