"""The cockpit agent: per-task structured Claude Agent SDK calls.

Each task is ONE ``query()`` call with its own ``output_format`` (the SDK
exposes structured output only at call construction). All calls share the same
correct configuration via ``build_options``: the ``claude_code`` system-prompt
preset and ``setting_sources=["project"]`` so CLAUDE.md, the project skills, and
the guardrail files actually govern the agent — the configuration the Plan 1
spike was missing.
"""
from __future__ import annotations

from typing import Any

from claude_agent_sdk import ClaudeAgentOptions

# Hard restatement layered on top of the loaded CLAUDE.md, emphasizing the two
# rules the spike found the agent skipped on a bare one-shot call.
_APPEND = (
    "You are the ed-bot forum assistant operating the cockpit. Before drafting "
    "any answer you MUST load the relevant project guardrail file under "
    "~/.ed-bot/playbook/guardrails/ and respect its Never-Reveal items, and you "
    "MUST run the drafted answer through the humanizer before returning it. "
    "Return only the final, post-humanizer text in the required structured shape."
)


def build_options(*, schema: dict[str, Any], cwd: str) -> ClaudeAgentOptions:
    """Construct the correctly-configured options for one structured agent call."""
    return ClaudeAgentOptions(
        system_prompt={"type": "preset", "preset": "claude_code", "append": _APPEND},
        setting_sources=["project"],
        skills="all",
        cwd=cwd,
        permission_mode="acceptEdits",
        output_format={"type": "json_schema", "schema": schema},
    )
