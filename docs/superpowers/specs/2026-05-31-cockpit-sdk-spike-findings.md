# Cockpit SDK Spike — Findings (2026-05-31)

Result of Plan 1: the Claude Agent SDK proof-of-concept. The spike's job was to
de-risk the core assumption before building any UI: can the SDK run this
project's skills and return a schema-valid, humanized `DraftPayload` that
respects guardrails? Answer: **the plumbing works; two critical behaviors do
NOT come for free and must be engineered in Plan 2.**

## Environment

- `claude-agent-sdk` version: **0.2.87** (plan guessed 0.1.x; the jump did not
  break the API we use).
- Verified importable and used: `query`, `ClaudeAgentOptions`, `ResultMessage`.
  `ResultMessage.structured_output` is a real field and carries the parsed
  structured output.
- Auth: the SDK used the bundled Claude Code CLI / Max-plan subscription
  automatically. No API key was set or needed. Confirmed by a real call
  completing.

## What the spike PROVED (core assumptions hold)

1. **Skills + CLAUDE.md load.** With `ClaudeAgentOptions(setting_sources=["project"], skills="all", cwd=...)`,
   the agent knew about `ed-api`, `qmd`, `~/.ed-bot`, the Martingale guardrail
   file, and even the project's "NEEDS HUMAN" flagging convention. Skill
   discovery works.
2. **Structured output works.** The agent returned a schema-valid `DraftPayload`
   (`DraftPayload.model_json_schema()` → `output_format={"type":"json_schema","schema":...}`
   → `ResultMessage.structured_output` → `model_validate`). Both a refusal and a
   real answer validated against the model.
3. **Tool use works when the environment is right** (see Gap A). With the
   correct `cwd`, the agent ran the real workflow and produced a substantive,
   accurate answer to thread #207 (correct axis limits, the fill-forward-at-80
   behavior, per-figure expectations).
4. **Max-plan auth works.** Real agent calls completed with no API key.

## Critical gaps found (MUST be addressed in Plan 2)

### Gap A — the agent needs the real tool environment (cwd + token + config dir)

The first live run used `cwd="."` = the repo root `E:\workspaces\school\gt\ed-bot`,
which has **no `.env`**. The `ED_API_TOKEN` lives only in
`E:\workspaces\school\gt\ed\.env`. So `ed-api` could not authenticate, the agent
could not fetch the thread or read guardrails, and it (correctly) returned a
NEEDS-HUMAN refusal rather than hallucinating. This was a harness mistake, not
an SDK or model failure.

**Implication for Plan 2:** the SDK session must be configured so the agent's
tools actually work — point `cwd` (or `add_dirs` / `env`) at the directory where
`ed-api` loads its `.env` token, and ensure `~/.ed-bot` (knowledge base,
playbook, guardrails) is reachable. Re-running the spike with
`cwd=E:\workspaces\school\gt\ed` produced a real answer, confirming the fix
direction.

### Gap B — guardrail enforcement does NOT come for free

In the corrected re-run, the agent produced a good answer **but revealed
`18/38`** (the American-roulette win probability), which is an explicit
**Never-Reveal** item in `~/.ed-bot/playbook/guardrails/martingale.md`. The
returned `guardrails_checked` was empty (`[]`) — the agent drafted without
loading/applying the guardrail.

**Implication for Plan 2:** "the skills are present" is not enough. The session
must explicitly enforce guardrails — e.g. a system prompt that mandates loading
the project guardrail before drafting, and/or a post-draft verification pass
(a second agent turn or a checker) that fails/flags any answer that violates
Never-Reveal items. A cockpit that leaks `18/38` is worse than no cockpit. This
is the single most important thing the spike taught us.

### Gap C — the mandatory humanizer does NOT run reliably on the one-shot path

The corrected re-run's body contained an em dash (`—`), which the project bans
and the humanizer would have removed. The one-shot `query()` did not reliably
trigger the mandatory humanizer step that the interactive `ed-answer`/`ed-check`
skill flow enforces.

**Implication for Plan 2:** the humanizer must be made an explicit, enforced
stage of the agent's draft flow (not left to the agent's discretion) — e.g. a
required tool/turn in the loop, or a post-process that runs the humanizer skill
on the body before it becomes a `DraftPayload`. The `DraftPayload.body` the UI
receives must always be post-humanizer.

## Carried-over code-review notes (graduation TODOs from Plan 1 Task 4)

These were deferred from the spike (a throwaway-grade module) and should be done
when the spike logic graduates into the real agent loop in Plan 2:

- **Typed exception hierarchy.** `default_sdk_query` raises bare `RuntimeError`
  on empty structured output. Plan 2 should introduce typed errors
  (e.g. `AgentError`, `StructuredOutputError`) so the UI can route failures.
- **Tighten the `SdkQuery` type.** It is `Callable[..., Awaitable[dict]]`
  (loose `...`). The real signature is known (`prompt: str, schema: dict,
  cwd: str`); use a `Protocol` or concrete `Callable[[...], ...]` so injection
  mismatches surface at type-check time.
- **Top-level async test config.** Async support is currently a
  `tests/cockpit/conftest.py` `anyio_backend` fixture. If async tests spread,
  move to a top-level `anyio_mode = "auto"` in `pyproject.toml`.

## Net verdict

The architecture in the design spec is sound and the SDK supports it. Proceed to
Plan 2, but Plan 2's scope MUST include explicit engineering for Gap A (tool
environment), Gap B (guardrail enforcement + post-draft verification), and Gap C
(enforced humanizer stage). Do not treat "the agent has the skills" as
sufficient for either guardrails or the humanizer — both must be enforced
structurally.
