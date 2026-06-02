"""The cockpit agent: per-task structured Claude Agent SDK calls.

Each task is ONE ``query()`` call with its own ``output_format`` (the SDK
exposes structured output only at call construction). All calls share the same
correct configuration via ``build_options``: the ``claude_code`` system-prompt
preset and ``setting_sources=["project"]`` so CLAUDE.md, the project skills, and
the guardrail files actually govern the agent — the configuration the Plan 1
spike was missing.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions

# The agent's tools and knowledge live in ~/.ed-bot (config, knowledge base,
# playbook, guardrails). The SDK confines file access to cwd by default, so we
# must explicitly grant access to this directory or the agent cannot load
# guardrails or search the KB.
_ED_BOT_DIR = str(Path("~/.ed-bot").expanduser())

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
        add_dirs=[_ED_BOT_DIR],
        # bypassPermissions so the agent can run its tools (ed-api/qmd via Bash)
        # without a prompt in this headless cockpit. Acceptable here: it's our
        # own agent against our own tools, and the human reviews every draft
        # before it posts. acceptEdits only auto-approves file edits, not Bash.
        permission_mode="bypassPermissions",
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
shape. In the `original_content` field, put the FULL thread as fetched from \
ed-api in plain text: the student's opening post followed by every comment and \
reply already on the thread, in order, each labeled with who wrote it (e.g. \
"student", "staff", or the author name) so the human reviewer can read the \
whole conversation alongside your draft. Do not summarize it; include the \
verbatim text. Set the `thread_id` field to the thread's GLOBAL id (the `id` \
from `ed-api thread get`), not the course-local number. If you cannot fetch \
the thread or are unsure, return a body beginning with "NEEDS HUMAN".""".strip()

_GUARDRAIL_DIR = Path("~/.ed-bot/playbook/guardrails").expanduser()


def _scrub_conflicting_api_key() -> None:
    """Keep a stray ANTHROPIC_API_KEY out of the Agent SDK subprocess.

    The cockpit authenticates the agent via the Max-plan subscription, not an
    API key. But constructing ``EdClient`` (for posting) calls ``load_dotenv``,
    which loads the project ``.env`` (it carries ``ED_API_TOKEN``) and ALSO
    injects whatever else lives there, including an ``ANTHROPIC_API_KEY``. The
    SDK subprocess inherits the process environment, so a leaked (and often
    stale) key reaches the CLI and it fails with "Invalid API key". The SDK
    merges ``options.env`` ON TOP of the inherited env and offers no way to
    unset an inherited var, so the only reliable fix is to drop it here before
    launching the query.
    """
    os.environ.pop("ANTHROPIC_API_KEY", None)


async def default_sdk_query(*, prompt: str, schema: dict, cwd: str) -> dict:
    """Real one-shot structured SDK call with the correct cockpit options."""
    _scrub_conflicting_api_key()
    options = build_options(schema=schema, cwd=cwd)
    result: dict | None = None
    final: ResultMessage | None = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            final = message
            result = message.structured_output
            break
    if result is None:
        # Surface WHY (turn limit, mid-run error, etc.) instead of a generic
        # message, so a failed draft is diagnosable from the cockpit status line.
        if final is not None:
            raise RuntimeError(
                f"SDK returned no structured_output "
                f"(subtype={getattr(final, 'subtype', None)!r}, "
                f"is_error={getattr(final, 'is_error', None)!r}): "
                f"{getattr(final, 'result', None)!r}"
            )
        raise RuntimeError("SDK returned no result message")
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

_CHAT_PREAMBLE = """You are the ed-bot forum assistant operating the cockpit for \
EdStem course {course_id}. You are having an ongoing conversation with the user \
in the cockpit chat. Use the conversation so far for context (the user expects \
you to remember what was said earlier in this chat). Answer concisely and \
helpfully. You have the project tools (ed-api, qmd, the guardrails and playbook \
under ~/.ed-bot) available if you need them.""".strip()


def _build_chat_prompt(course_id: int, history: list[tuple[str, str]],
                       text: str) -> str:
    """Fold the conversation history + the new user message into one prompt.

    ``history`` is a list of (role, text) for prior turns, role in
    {"you", "ed-bot"}. The current user message is appended last."""
    lines = [_CHAT_PREAMBLE.format(course_id=course_id), "", "Conversation so far:"]
    for role, msg in history:
        speaker = "User" if role == "you" else "ed-bot"
        lines.append(f"{speaker}: {msg}")
    lines.append(f"User: {text}")
    lines.append("ed-bot:")
    return "\n".join(lines)


async def default_sdk_text(*, prompt: str, cwd: str) -> str:
    """Plain (non-structured) SDK call; returns the concatenated assistant text."""
    _scrub_conflicting_api_key()
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
    history: list[tuple[str, str]] | None = None,
    sdk_text: SdkText = default_sdk_text,
) -> str:
    """Produce a freeform conversational reply, with prior-turn context."""
    prompt = _build_chat_prompt(course_id, history or [], text)
    return await sdk_text(prompt=prompt, cwd=cwd)
