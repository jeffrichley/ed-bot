"""Tests for the cockpit agent's SDK options builder."""
from ed_bot.cockpit.agent import build_options


def test_build_options_loads_project_and_preset():
    schema = {"type": "object", "properties": {}}
    opts = build_options(schema=schema, cwd="/some/ed/dir")
    # claude_code preset so CLAUDE.md + project rules load
    assert opts.system_prompt["type"] == "preset"
    assert opts.system_prompt["preset"] == "claude_code"
    assert "guardrail" in opts.system_prompt["append"].lower()
    assert "humanizer" in opts.system_prompt["append"].lower()
    # project settings (CLAUDE.md, .claude/skills) load
    assert opts.setting_sources == ["project"]
    assert opts.skills == "all"
    assert opts.cwd == "/some/ed/dir"
    assert opts.permission_mode == "acceptEdits"
    assert opts.output_format == {"type": "json_schema", "schema": schema}
