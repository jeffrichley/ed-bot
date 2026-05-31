"""Proof-of-concept: turn a WatcherEvent into a humanized DraftPayload via the
Claude Agent SDK. The actual SDK call is injected (``sdk_query``) so the logic
is unit-testable; ``default_sdk_query`` performs the real call."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

from ed_bot.cockpit.models import WatcherEvent, DraftPayload

SdkQuery = Callable[..., Awaitable[dict[str, Any]]]

_PROMPT = """You are the ed-bot forum assistant. A new EdStem thread needs an \
answer. Use your ed-answer workflow: read the thread, check the project \
guardrails, draft an answer, and run it through the humanizer. Return ONLY the \
final, post-humanizer answer in the required structured shape.

Thread #{number}: "{title}"
Category: {category}
URL: {url}
""".strip()


async def default_sdk_query(*, prompt: str, schema: dict, cwd: str) -> dict:
    """Real SDK call: run a one-shot query with structured output, loading this
    project's skills and settings. Returns the structured_output dict."""
    options = ClaudeAgentOptions(
        cwd=cwd,
        permission_mode="acceptEdits",
        setting_sources=["project"],
        skills="all",
        output_format={"type": "json_schema", "schema": schema},
    )
    result: dict | None = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result = message.structured_output
    if result is None:
        raise RuntimeError("SDK returned no structured_output")
    return result


async def draft_for_event(
    event: WatcherEvent,
    *,
    cwd: str,
    sdk_query: SdkQuery = default_sdk_query,
) -> DraftPayload:
    """Produce a validated, humanized DraftPayload for a forum event."""
    prompt = _PROMPT.format(
        number=event.number, title=event.title,
        category=event.category, url=event.url,
    )
    schema = DraftPayload.model_json_schema()
    raw = await sdk_query(prompt=prompt, schema=schema, cwd=cwd)
    return DraftPayload.model_validate(raw)
