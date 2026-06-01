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


from pathlib import Path
from typing import Awaitable, Callable

from claude_agent_sdk import query, ResultMessage
from ed_bot.cockpit.models import DraftPayload
from ed_bot.cockpit.guardrail_scan import scan_body as _default_scan

SdkQuery = Callable[..., Awaitable[dict[str, Any]]]
GuardrailScan = Callable[[str, Path], list[str]]

_DRAFT_PROMPT = """A forum thread needs an answer. Run the full workflow for \
EdStem thread #{number} in course {course_id}: fetch the thread with ed-api, \
search the knowledge base, load the project guardrail, draft an answer, and run \
the humanizer. Return only the final post-humanizer answer in the structured \
shape. If you cannot fetch the thread or are unsure, return a body beginning \
with "NEEDS HUMAN".""".strip()

_GUARDRAIL_DIR = Path("~/.ed-bot/playbook/guardrails").expanduser()


async def default_sdk_query(*, prompt: str, schema: dict, cwd: str) -> dict:
    """Real one-shot structured SDK call with the correct cockpit options."""
    options = build_options(schema=schema, cwd=cwd)
    result: dict | None = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result = message.structured_output
            break
    if result is None:
        raise RuntimeError("SDK returned no structured_output")
    return result


def _guardrail_path_for(project: str | None) -> Path:
    """Map a project label to its guardrail file (best-effort)."""
    if not project:
        return _GUARDRAIL_DIR / "__none__.md"
    slug = project.lower()
    if "martingale" in slug:
        return _GUARDRAIL_DIR / "martingale.md"
    if "optimize" in slug:
        return _GUARDRAIL_DIR / "optimize-something.md"
    # Fallback: a non-existent path -> scan returns [] (advisory stays silent).
    return _GUARDRAIL_DIR / "__none__.md"


async def draft_thread(
    *,
    number: int,
    cwd: str,
    course_id: int,
    sdk_query: SdkQuery = default_sdk_query,
    guardrail_scan: GuardrailScan = _default_scan,
) -> DraftPayload:
    """Draft an answer for a thread and attach advisory guardrail warnings."""
    prompt = _DRAFT_PROMPT.format(number=number, course_id=course_id)
    schema = DraftPayload.model_json_schema()
    raw = await sdk_query(prompt=prompt, schema=schema, cwd=cwd)
    payload = DraftPayload.model_validate(raw)
    warnings = guardrail_scan(payload.body, _guardrail_path_for(payload.project))
    return payload.model_copy(update={"guardrail_warnings": warnings})


from claude_agent_sdk import AssistantMessage, TextBlock

SdkText = Callable[..., Awaitable[str]]

_CHAT_PROMPT = """You are the ed-bot forum assistant operating the cockpit for \
EdStem course {course_id}. The user is talking to you in the cockpit chat. \
Answer concisely and helpfully. You have the project tools (ed-api, qmd, the \
guardrails and playbook under ~/.ed-bot) available if you need them.

User: {text}""".strip()


async def default_sdk_text(*, prompt: str, cwd: str) -> str:
    """Plain (non-structured) SDK call; returns the concatenated assistant text."""
    options = build_options(schema={"type": "object"}, cwd=cwd)
    # Reuse the correct cockpit config but ignore structured output for chat.
    options.output_format = None
    chunks: list[str] = []
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    chunks.append(block.text)
    return "".join(chunks).strip()


async def chat_reply(
    *,
    text: str,
    cwd: str,
    course_id: int,
    sdk_text: SdkText = default_sdk_text,
) -> str:
    """Produce a freeform conversational reply for the cockpit chat."""
    prompt = _CHAT_PROMPT.format(course_id=course_id, text=text)
    return await sdk_text(prompt=prompt, cwd=cwd)
