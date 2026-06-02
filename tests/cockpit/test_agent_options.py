"""Tests for the cockpit agent's SDK options builder."""
from ed_bot.cockpit.agent import build_options


def test_build_options_loads_project_and_preset():
    schema = {"type": "object", "properties": {}}
    opts = build_options(schema=schema, cwd="/some/ed/dir")
    # claude_code preset so CLAUDE.md + project rules load
    assert opts.system_prompt["type"] == "preset"
    assert opts.system_prompt["preset"] == "claude_code"
    assert "guardrail" in opts.system_prompt["append"].lower()
    # The append still mandates humanizing; the full rule list is injected into
    # the draft prompt (see test_agent_humanizer), so the append references the
    # human-writing requirement rather than a "humanizer" tool.
    assert "humanized" in opts.system_prompt["append"].lower()
    # project settings (CLAUDE.md, .claude/skills) load
    assert opts.setting_sources == ["project"]
    assert opts.skills == "all"
    assert opts.cwd == "/some/ed/dir"
    # bypassPermissions so the agent can run ed-api/qmd (Bash) headlessly.
    assert opts.permission_mode == "bypassPermissions"
    assert opts.output_format == {"type": "json_schema", "schema": schema}
    # The agent must be granted access to ~/.ed-bot (knowledge base, playbook,
    # guardrails) beyond cwd, or it can't load guardrails / search the KB.
    from pathlib import Path
    ed_bot_dir = str(Path("~/.ed-bot").expanduser())
    assert ed_bot_dir in opts.add_dirs
