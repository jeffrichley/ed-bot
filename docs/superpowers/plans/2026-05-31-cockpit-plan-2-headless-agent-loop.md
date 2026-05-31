# Cockpit Plan 2 — Headless Agent Loop + Async Watcher — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the cockpit's headless brain: an asyncio loop where a watcher task and user commands feed one queue, a router dispatches each to a per-task Claude Agent SDK `query()` call (correctly configured to load CLAUDE.md + project skills), and typed Pydantic results flow back out — all driven by a test harness, no Textual UI yet.

**Architecture:** One asyncio process. Producers (watcher task, user-command injector) put messages on an `asyncio.Queue`. A single consumer task routes each message to the matching agent function in `cockpit.agent`. Each agent function is ONE `query()` call with its own `output_format` (the SDK exposes structured output only at call construction, so we use one structured call per task rather than a persistent varying-schema session). The agent session is configured with the `claude_code` system-prompt preset + `setting_sources=["project"]` + `cwd` at the ed dir so CLAUDE.md, skills, guardrails, and the `ed-api` token all load — the misconfiguration the Plan 1 spike exposed.

**Tech Stack:** Python 3.12, asyncio, claude-agent-sdk 0.2.87, Pydantic v2, pytest + anyio.

**Spec:** `docs/superpowers/specs/2026-05-31-ed-cockpit-tui-design.md`
**Spike findings (REQUIRED READING):** `docs/superpowers/specs/2026-05-31-cockpit-sdk-spike-findings.md`

---

## Key decisions baked into this plan (read before starting)

1. **No persistent varying-schema session.** The SDK's `output_format` is a
   construction-time option; there is no documented per-turn schema switch. So
   each agent task is its own `query()` call with its own `output_format`.
   Cross-turn "conversation" is reconstructed by the cockpit (UI/transcript
   state in Plan 3), not held in one SDK session. This is a deliberate
   deviation from the spec's "single long-lived conversation" phrasing; same
   user-facing behavior, better SDK fit. (Spec addendum task at the end.)
2. **Correct SDK config is mandatory** (fixes spike Gap A/B/C at the config
   level): `system_prompt={"type":"preset","preset":"claude_code","append": <hard rules>}`,
   `setting_sources=["project"]`, `skills="all"`, `cwd=<ed dir>`,
   `permission_mode="acceptEdits"`, plus the per-task `output_format`.
3. **No hard guardrail gate.** The human reviews every draft before it posts
   (Plan 3), so we do NOT block on guardrail hits. We DO surface a cheap
   advisory flag (a non-blocking `guardrail_warnings` list on the draft) to
   speed review. Advisory only.
4. **Tailored cockpit prompts**, not the `/ed-answer` skill wrapper — we drive
   the underlying tools in a sequence we control for granular status.
5. **The agent runs from the ed dir** (`E:\workspaces\school\gt\ed`), resolved
   from config, NOT hardcoded.

---

## File Structure

- `src/ed_bot/cockpit/config.py` — resolves runtime paths: the ed working dir
  (where `.env` lives), the active course_id from `~/.ed-bot/config.yaml`.
- `src/ed_bot/cockpit/agent.py` — the agent task functions: `classify_event`,
  `draft_thread`, `post_draft`. Each builds options + does one `query()`. SDK
  call injected for tests.
- `src/ed_bot/cockpit/guardrail_scan.py` — advisory Never-Reveal scan: load a
  project's guardrail file, return any matched tokens found in a body.
- `src/ed_bot/cockpit/loop.py` — the asyncio queue, the consumer/router, the
  command→task dispatch, and the auto-draft state tracking.
- `src/ed_bot/cockpit/watcher.py` — the async watcher task (polls EdStem, emits
  WatcherEvent onto the queue). Wraps the sync ed-api client via
  `asyncio.to_thread`.
- `src/ed_bot/cockpit/models.py` — MODIFY: add advisory `guardrail_warnings`
  field to DraftPayload.
- Tests mirror each under `tests/cockpit/`.

---

## Task 1: Runtime config resolution

**Files:**
- Create: `src/ed_bot/cockpit/config.py`
- Test: `tests/cockpit/test_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/cockpit/test_config.py`:

```python
"""Tests for cockpit runtime config resolution."""
import textwrap

from ed_bot.cockpit.config import resolve_course_id, ed_working_dir


def test_resolve_course_id_reads_top_level_key(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(textwrap.dedent("""
        course_id: 98559
        region: us
        semesters:
          - name: summer-2026
            course_id: 98559
    """).strip(), encoding="utf-8")
    assert resolve_course_id(cfg) == 98559


def test_resolve_course_id_missing_raises(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("region: us\n", encoding="utf-8")
    try:
        resolve_course_id(cfg)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_ed_working_dir_is_absolute_and_named_ed():
    p = ed_working_dir()
    assert p.name == "ed"
    assert p.is_absolute()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_config.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'ed_bot.cockpit.config'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/ed_bot/cockpit/config.py`:

```python
"""Resolve cockpit runtime paths and the active course, never hardcoded.

The agent must run from the directory where ``ed-api`` loads its ``.env`` token
(the sibling ``ed`` working dir), and the active course comes from
``~/.ed-bot/config.yaml`` — both resolved here.
"""
from __future__ import annotations

import re
from pathlib import Path

_DEFAULT_CONFIG = Path("~/.ed-bot/config.yaml").expanduser()


def resolve_course_id(config_path: Path = _DEFAULT_CONFIG) -> int:
    """Read the top-level ``course_id:`` from the ed-bot config file."""
    text = Path(config_path).read_text(encoding="utf-8")
    m = re.search(r"^course_id:\s*(\d+)", text, re.MULTILINE)
    if not m:
        raise ValueError(f"no top-level course_id in {config_path}")
    return int(m.group(1))


def ed_working_dir() -> Path:
    """The sibling ``ed`` directory that holds the ``.env`` API token.

    The cockpit lives in the ``ed-bot`` repo; the runnable CLI workspace with
    the token is its sibling ``ed`` directory.
    """
    repo_root = Path(__file__).resolve().parents[3]  # .../ed-bot
    return (repo_root.parent / "ed").resolve()
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_config.py -q`
Expected: PASS (3 passed). Note: `test_ed_working_dir_is_absolute_and_named_ed` only checks the name/shape, not existence, so it passes regardless of the machine.

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/config.py tests/cockpit/test_config.py
git commit -m "feat(cockpit): resolve ed working dir and active course_id"
```

---

## Task 2: Advisory guardrail scan

**Files:**
- Create: `src/ed_bot/cockpit/guardrail_scan.py`
- Test: `tests/cockpit/test_guardrail_scan.py`

This is advisory only (the human reviews every draft). It extracts the literal
Never-Reveal tokens worth flagging from a guardrail markdown file and reports
which appear in a draft body.

- [ ] **Step 1: Write the failing test**

Create `tests/cockpit/test_guardrail_scan.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_guardrail_scan.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Create `src/ed_bot/cockpit/guardrail_scan.py`:

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_guardrail_scan.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/guardrail_scan.py tests/cockpit/test_guardrail_scan.py
git commit -m "feat(cockpit): add advisory Never-Reveal guardrail scan"
```

---

## Task 3: Add advisory guardrail_warnings to DraftPayload

**Files:**
- Modify: `src/ed_bot/cockpit/models.py`
- Test: `tests/cockpit/test_models.py` (and update the exact-field-set invariant test)

- [ ] **Step 1: Update the failing test**

In `tests/cockpit/test_models.py`, the `test_draft_payload_is_humanized_only`
test asserts an EXACT field set. Add `"guardrail_warnings"` to the `expected`
set so it reads:

```python
    expected = {
        "thread_id", "number", "question", "body", "is_canned", "project",
        "guardrails_checked", "confidence", "post_kind", "target_comment_id",
        "guardrail_warnings",
    }
```

Then append a new test to the file:

```python
def test_draft_payload_guardrail_warnings_default_empty():
    d = DraftPayload(
        thread_id=1, number=1, question="q", body="b",
    )
    assert d.guardrail_warnings == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_models.py -q`
Expected: FAIL — the exact-field-set assertion fails because `guardrail_warnings` isn't a field yet, and the new test errors.

- [ ] **Step 3: Implement**

In `src/ed_bot/cockpit/models.py`, add to the `DraftPayload` class a field
(place it after `target_comment_id`):

```python
    guardrail_warnings: list[str] = []
```

Update the `DraftPayload` docstring to add a sentence:

```python
    """A drafted reply for one thread. ``body`` is ALWAYS the final,
    post-humanizer text. There is deliberately no raw-draft field: the UI must
    never be able to display pre-humanizer content. ``guardrail_warnings`` is an
    advisory, non-blocking list of possible Never-Reveal hits to speed review."""
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_models.py -q`
Expected: PASS (12 passed: 11 prior — the humanized-only test still passing with the updated field set — plus the new `test_draft_payload_guardrail_warnings_default_empty` test).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/models.py tests/cockpit/test_models.py
git commit -m "feat(cockpit): add advisory guardrail_warnings to DraftPayload"
```

---

## Task 4: The agent options builder (correct SDK config)

**Files:**
- Modify: `src/ed_bot/cockpit/agent.py` (create it)
- Test: `tests/cockpit/test_agent_options.py`

This isolates the CORRECT SDK configuration (the spike's fix) in one tested
function, so every agent task uses it identically.

- [ ] **Step 1: Write the failing test**

Create `tests/cockpit/test_agent_options.py`:

```python
"""Tests for the cockpit agent's SDK options builder."""
from ed_bot.cockpit.agent import build_options


def test_build_options_loads_project_and_preset():
    schema = {"type": "object", "properties": {}}
    opts = build_options(schema=schema, cwd="/some/ed/dir")
    # claude_code preset so CLAUDE.md + project rules load
    assert opts.system_prompt["type"] == "preset"
    assert opts.system_prompt["preset"] == "claude_code"
    assert "guardrail" in opts.system_prompt["append"].lower()
    # project settings (CLAUDE.md, .claude/skills) load
    assert opts.setting_sources == ["project"]
    assert opts.skills == "all"
    assert opts.cwd == "/some/ed/dir"
    assert opts.permission_mode == "acceptEdits"
    assert opts.output_format == {"type": "json_schema", "schema": schema}
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_agent_options.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'ed_bot.cockpit.agent'`.

- [ ] **Step 3: Implement**

Create `src/ed_bot/cockpit/agent.py`:

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_agent_options.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/agent.py tests/cockpit/test_agent_options.py
git commit -m "feat(cockpit): add correctly-configured agent options builder"
```

---

## Task 5: The draft_thread agent task (injected SDK)

**Files:**
- Modify: `src/ed_bot/cockpit/agent.py`
- Test: `tests/cockpit/test_agent_draft.py`

`draft_thread` takes a thread number, builds a tailored prompt, calls the SDK
(injected) for a `DraftPayload`, then runs the advisory guardrail scan and
attaches warnings. SDK injected for tests.

- [ ] **Step 1: Write the failing test**

Create `tests/cockpit/test_agent_draft.py`:

```python
"""Tests for the draft_thread agent task with a fake SDK and fake guardrail scan."""
import pytest

from ed_bot.cockpit.models import DraftPayload
from ed_bot.cockpit import agent


def _raw_draft(**over):
    base = dict(
        thread_id=8104866, number=207, question="How is Figure 1 graded?",
        body="Plot 10 episodes with the required axis limits.",
        is_canned=False, project="Project 1 - Martingale",
        guardrails_checked=["martingale"], confidence="HIGH",
        post_kind="answer", target_comment_id=None,
    )
    base.update(over)
    return base


@pytest.mark.anyio
async def test_draft_thread_attaches_no_warnings_for_clean_body():
    async def fake_sdk(*, prompt, schema, cwd):
        assert "207" in prompt
        return _raw_draft()

    def fake_scan(body, gpath):
        return []

    payload = await agent.draft_thread(
        number=207, cwd=".", course_id=98559,
        sdk_query=fake_sdk, guardrail_scan=fake_scan,
    )
    assert isinstance(payload, DraftPayload)
    assert payload.guardrail_warnings == []


@pytest.mark.anyio
async def test_draft_thread_attaches_advisory_warnings():
    async def fake_sdk(*, prompt, schema, cwd):
        return _raw_draft(body="win probability is 18/38")

    def fake_scan(body, gpath):
        return ["possible Never-Reveal leak: 18/38"] if "18/38" in body else []

    payload = await agent.draft_thread(
        number=207, cwd=".", course_id=98559,
        sdk_query=fake_sdk, guardrail_scan=fake_scan,
    )
    assert payload.guardrail_warnings == ["possible Never-Reveal leak: 18/38"]
    # Advisory only: the draft is still returned, NOT blocked.
    assert payload.body == "win probability is 18/38"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_agent_draft.py -q`
Expected: FAIL with `AttributeError: module 'ed_bot.cockpit.agent' has no attribute 'draft_thread'`.

- [ ] **Step 3: Implement**

Append to `src/ed_bot/cockpit/agent.py`:

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_agent_draft.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/agent.py tests/cockpit/test_agent_draft.py
git commit -m "feat(cockpit): add draft_thread agent task with advisory guardrail scan"
```

---

## Task 6: The async queue + consumer/router with auto-draft

**Files:**
- Create: `src/ed_bot/cockpit/loop.py`
- Test: `tests/cockpit/test_loop.py`

The loop holds an `asyncio.Queue`, a registry of `QueueItem`s keyed by thread,
and a consumer that routes each message. A new `WatcherEvent` classified as
actionable creates a `QueueItem` (draft_state="drafting") and kicks off an
auto-draft that flips it to "ready" with the payload attached. Outbound results
are pushed to an injected `emit` callback (Plan 3 wires this to Textual).

- [ ] **Step 1: Write the failing test**

Create `tests/cockpit/test_loop.py`:

```python
"""Tests for the headless cockpit loop: routing, auto-draft, state."""
import asyncio
import pytest

from ed_bot.cockpit.models import (
    WatcherEvent, UserCommand, DraftPayload, QueueUpdate, DraftState,
)
from ed_bot.cockpit.loop import CockpitLoop


def _event(number=207, kind="new_thread"):
    return WatcherEvent(
        kind=kind, thread_id=8100000 + number, number=number,
        title=f"thread {number}", category="Project 1 | Martingale",
        url=f"https://edstem.org/x/{number}",
    )


def _payload(number=207):
    return DraftPayload(
        thread_id=8100000 + number, number=number, question="q",
        body="clean body", project="Project 1 - Martingale",
        confidence="HIGH",
    )


@pytest.mark.anyio
async def test_new_event_creates_queue_item_then_autodrafts():
    emitted = []

    async def fake_draft(*, number, **kw):
        return _payload(number)

    loop = CockpitLoop(
        cwd=".", course_id=98559,
        draft_fn=fake_draft, emit=lambda m: emitted.append(m),
    )
    await loop.handle(_event(207))

    # A QueueItem was created and ended in 'ready' with a draft.
    item = loop.queue_item(207)
    assert item is not None
    assert item.draft_state == "ready"
    assert loop.draft(207).body == "clean body"
    # Emitted at least one QueueUpdate.
    assert any(isinstance(m, QueueUpdate) for m in emitted)


@pytest.mark.anyio
async def test_escalation_event_is_high_urgency():
    async def fake_draft(*, number, **kw):
        return _payload(number)
    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=fake_draft,
                       emit=lambda m: None)
    await loop.handle(_event(166, kind="escalation"))
    assert loop.queue_item(166).urgency == "high"


@pytest.mark.anyio
async def test_draft_failure_sets_failed_state():
    async def boom(*, number, **kw):
        raise RuntimeError("sdk down")
    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=boom,
                       emit=lambda m: None)
    await loop.handle(_event(207))
    assert loop.queue_item(207).draft_state == "failed"


@pytest.mark.anyio
async def test_open_command_returns_existing_draft():
    async def fake_draft(*, number, **kw):
        return _payload(number)
    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=fake_draft,
                       emit=lambda m: None)
    await loop.handle(_event(207))
    # 'open' should not redraft; the draft is already ready.
    got = await loop.handle(UserCommand(intent="open", thread=207))
    assert got.number == 207
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_loop.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'ed_bot.cockpit.loop'`.

- [ ] **Step 3: Implement**

Create `src/ed_bot/cockpit/loop.py`:

```python
"""The headless cockpit loop: one queue, one consumer/router, auto-draft.

Producers (the watcher task, user-command injection) hand messages to
``handle``. A new actionable WatcherEvent creates a QueueItem and auto-drafts
it; user commands act on existing items. Outbound typed results go to the
injected ``emit`` callback (Plan 3 wires it to Textual widgets)."""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional

from ed_bot.cockpit.models import (
    WatcherEvent, UserCommand, QueueItem, QueueUpdate, DraftPayload, StatusUpdate,
)

DraftFn = Callable[..., Awaitable[DraftPayload]]
Emit = Callable[[Any], None]

_SILENT_CATEGORIES = {"Social >", "Announcements", "Articles | Papers | Media"}


class CockpitLoop:
    def __init__(self, *, cwd: str, course_id: int, draft_fn: DraftFn,
                 emit: Emit) -> None:
        self._cwd = cwd
        self._course_id = course_id
        self._draft_fn = draft_fn
        self._emit = emit
        self._items: dict[int, QueueItem] = {}
        self._drafts: dict[int, DraftPayload] = {}

    # --- read accessors (Plan 3 / tests) ---
    def queue_item(self, number: int) -> Optional[QueueItem]:
        return self._items.get(number)

    def draft(self, number: int) -> Optional[DraftPayload]:
        return self._drafts.get(number)

    def _push_queue(self) -> None:
        self._emit(QueueUpdate(items=list(self._items.values())))

    def _is_actionable(self, ev: WatcherEvent) -> bool:
        if ev.kind in ("error", "recovered"):
            return False
        if ev.category in _SILENT_CATEGORIES and "?" not in ev.title:
            return False
        return True

    async def handle(self, msg: WatcherEvent | UserCommand):
        if isinstance(msg, WatcherEvent):
            return await self._on_event(msg)
        return await self._on_command(msg)

    async def _on_event(self, ev: WatcherEvent) -> None:
        if not self._is_actionable(ev):
            return
        item = QueueItem(
            thread_id=ev.thread_id, number=ev.number, title=ev.title,
            category=ev.category, kind=ev.kind,
            urgency="high" if ev.kind == "escalation" else "normal",
            draft_state="drafting", status="needs_attention",
        )
        self._items[ev.number] = item
        self._push_queue()
        await self._autodraft(ev.number)

    async def _autodraft(self, number: int) -> None:
        self._emit(StatusUpdate(line=f"drafting #{number}..."))
        try:
            payload = await self._draft_fn(
                number=number, cwd=self._cwd, course_id=self._course_id,
            )
        except Exception as e:  # noqa: BLE001 - surface as failed state
            self._items[number] = self._items[number].model_copy(
                update={"draft_state": "failed"})
            self._emit(StatusUpdate(line=f"draft #{number} failed: {e}"))
            self._push_queue()
            return
        self._drafts[number] = payload
        self._items[number] = self._items[number].model_copy(
            update={"draft_state": "ready"})
        self._emit(StatusUpdate(line=f"#{number} ready"))
        self._push_queue()

    async def _on_command(self, cmd: UserCommand) -> Optional[DraftPayload]:
        if cmd.intent == "open" and cmd.thread is not None:
            return self._drafts.get(cmd.thread)
        # Other intents (approve/edit/reject/...) are wired in Task 7+.
        return None
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_loop.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/loop.py tests/cockpit/test_loop.py
git commit -m "feat(cockpit): headless loop with routing and auto-draft state machine"
```

---

## Task 7: The post action with staleness re-check

**Files:**
- Modify: `src/ed_bot/cockpit/agent.py`, `src/ed_bot/cockpit/loop.py`
- Test: `tests/cockpit/test_loop_post.py`

Approving a draft posts it. Before posting, re-check the thread is still
unanswered (the spike-era staleness bug). Posting + accept run via an injected
`post_fn` (so tests don't hit ed-api).

- [ ] **Step 1: Write the failing test**

Create `tests/cockpit/test_loop_post.py`:

```python
"""Tests for approve/post flow with staleness re-check."""
import pytest

from ed_bot.cockpit.models import WatcherEvent, UserCommand, DraftPayload, ActionResult
from ed_bot.cockpit.loop import CockpitLoop


def _event(number=207):
    return WatcherEvent(
        kind="new_thread", thread_id=8100000 + number, number=number,
        title=f"t{number}", category="Project 1 | Martingale",
        url=f"https://edstem.org/x/{number}",
    )


def _payload(number=207):
    return DraftPayload(thread_id=8100000 + number, number=number,
                        question="q", body="b", confidence="HIGH")


async def _draft(*, number, **kw):
    return _payload(number)


@pytest.mark.anyio
async def test_approve_posts_and_marks_posted():
    posted = {}

    async def fake_post(*, number, body, post_kind, target_comment_id):
        posted["called"] = number
        return ActionResult(thread_id=8100000 + number, ok=True,
                            posted_id=999, accepted=True, message="ok")

    async def fresh_is_answered(number):
        return False  # still open

    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=_draft,
                       emit=lambda m: None, post_fn=fake_post,
                       is_answered_fn=fresh_is_answered)
    await loop.handle(_event(207))
    res = await loop.handle(UserCommand(intent="approve", thread=207))

    assert isinstance(res, ActionResult)
    assert res.ok and res.accepted
    assert posted["called"] == 207
    assert loop.queue_item(207).status == "posted"


@pytest.mark.anyio
async def test_approve_skips_post_when_already_answered():
    async def fake_post(*, number, body, post_kind, target_comment_id):
        raise AssertionError("must not post a stale thread")

    async def stale_is_answered(number):
        return True  # staff already answered

    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=_draft,
                       emit=lambda m: None, post_fn=fake_post,
                       is_answered_fn=stale_is_answered)
    await loop.handle(_event(207))
    res = await loop.handle(UserCommand(intent="approve", thread=207))

    assert res.ok is False
    assert "already answered" in res.message.lower()
    assert loop.queue_item(207).status != "posted"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_loop_post.py -q`
Expected: FAIL — `CockpitLoop.__init__` does not accept `post_fn` / `is_answered_fn`.

- [ ] **Step 3: Implement**

In `src/ed_bot/cockpit/loop.py`, extend `__init__` to accept and store two more
injected callables (default `None`), and add the approve handling. Update the
imports and `__init__`:

```python
from ed_bot.cockpit.models import (
    WatcherEvent, UserCommand, QueueItem, QueueUpdate, DraftPayload, StatusUpdate,
    ActionResult,
)

PostFn = Callable[..., Awaitable[ActionResult]]
IsAnsweredFn = Callable[[int], Awaitable[bool]]
```

Extend `__init__` signature and body:

```python
    def __init__(self, *, cwd: str, course_id: int, draft_fn: DraftFn,
                 emit: Emit, post_fn: "PostFn | None" = None,
                 is_answered_fn: "IsAnsweredFn | None" = None) -> None:
        self._cwd = cwd
        self._course_id = course_id
        self._draft_fn = draft_fn
        self._emit = emit
        self._post_fn = post_fn
        self._is_answered_fn = is_answered_fn
        self._items: dict[int, QueueItem] = {}
        self._drafts: dict[int, DraftPayload] = {}
```

Replace the `_on_command` method with:

```python
    async def _on_command(self, cmd: UserCommand):
        if cmd.intent == "open" and cmd.thread is not None:
            return self._drafts.get(cmd.thread)
        if cmd.intent == "approve" and cmd.thread is not None:
            return await self._approve(cmd.thread)
        return None

    async def _approve(self, number: int) -> ActionResult:
        payload = self._drafts.get(number)
        if payload is None:
            return ActionResult(thread_id=0, ok=False, message="no draft to post")
        if self._is_answered_fn is not None and await self._is_answered_fn(number):
            self._emit(StatusUpdate(line=f"#{number} already answered, skipped"))
            return ActionResult(thread_id=payload.thread_id, ok=False,
                                message="thread already answered, not posting")
        assert self._post_fn is not None, "post_fn required to approve"
        res = await self._post_fn(
            number=number, body=payload.body, post_kind=payload.post_kind,
            target_comment_id=payload.target_comment_id,
        )
        if res.ok:
            self._items[number] = self._items[number].model_copy(
                update={"status": "posted"})
            self._emit(StatusUpdate(line=f"posted #{number}"))
            self._push_queue()
        return res
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_loop_post.py -q`
Expected: PASS (2 passed). Also run `.venv/Scripts/python.exe -m pytest tests/cockpit/test_loop.py -q` to confirm Task 6 still passes (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/loop.py tests/cockpit/test_loop_post.py
git commit -m "feat(cockpit): approve flow posts with staleness re-check"
```

---

## Task 8: The async watcher task

**Files:**
- Create: `src/ed_bot/cockpit/watcher.py`
- Test: `tests/cockpit/test_watcher.py`

A coroutine that polls on an interval and puts WatcherEvents on an
`asyncio.Queue`. The sync forum fetch is injected (real wiring wraps the sync
ed-api client via `asyncio.to_thread`). One-shot `poll_once` is the unit;
the long-running loop is a thin wrapper.

- [ ] **Step 1: Write the failing test**

Create `tests/cockpit/test_watcher.py`:

```python
"""Tests for the async watcher task."""
import asyncio
import pytest

from ed_bot.cockpit.models import WatcherEvent
from ed_bot.cockpit.watcher import poll_once


@pytest.mark.anyio
async def test_poll_once_puts_events_on_queue():
    q: asyncio.Queue = asyncio.Queue()

    async def fake_fetch_events(course_id):
        return [
            WatcherEvent(kind="new_thread", thread_id=1, number=207,
                         title="t", category="Project 1 | Martingale",
                         url="u"),
        ]

    await poll_once(course_id=98559, queue=q, fetch_events=fake_fetch_events)
    assert q.qsize() == 1
    ev = await q.get()
    assert ev.number == 207


@pytest.mark.anyio
async def test_poll_once_tolerates_fetch_failure():
    q: asyncio.Queue = asyncio.Queue()

    async def boom(course_id):
        raise RuntimeError("api down")

    # Must not raise; a transient poll failure should be swallowed.
    await poll_once(course_id=98559, queue=q, fetch_events=boom)
    assert q.qsize() == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_watcher.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'ed_bot.cockpit.watcher'`.

- [ ] **Step 3: Implement**

Create `src/ed_bot/cockpit/watcher.py`:

```python
"""The async watcher task: poll EdStem, put WatcherEvents on the queue.

The forum fetch is injected. The real wiring wraps the synchronous ed-api
client with ``asyncio.to_thread`` so the poll never blocks the event loop."""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from ed_bot.cockpit.models import WatcherEvent

log = logging.getLogger(__name__)

FetchEvents = Callable[[int], Awaitable[list[WatcherEvent]]]


async def poll_once(*, course_id: int, queue: "asyncio.Queue",
                    fetch_events: FetchEvents) -> None:
    """One poll cycle: fetch actionable events and enqueue them. Swallows
    transient fetch failures so the watcher loop survives."""
    try:
        events = await fetch_events(course_id)
    except Exception as e:  # noqa: BLE001 - one bad poll must not kill the loop
        log.warning("watcher poll failed: %s", e)
        return
    for ev in events:
        await queue.put(ev)


async def watch_loop(*, course_id: int, queue: "asyncio.Queue",
                     fetch_events: FetchEvents, interval_seconds: float,
                     stop: "asyncio.Event") -> None:
    """Poll on an interval until ``stop`` is set."""
    while not stop.is_set():
        await poll_once(course_id=course_id, queue=queue,
                        fetch_events=fetch_events)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_watcher.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/watcher.py tests/cockpit/test_watcher.py
git commit -m "feat(cockpit): async watcher task with fault-tolerant polling"
```

---

## Task 9: Headless end-to-end harness test

**Files:**
- Test: `tests/cockpit/test_headless_e2e.py`

Wire the watcher → queue → loop together with fakes and prove the whole
headless path: an event flows in, gets auto-drafted, lands ready in the queue,
and an approve posts it. No SDK, no network.

- [ ] **Step 1: Write the test**

Create `tests/cockpit/test_headless_e2e.py`:

```python
"""End-to-end headless wiring: watcher queue -> loop -> auto-draft -> approve."""
import asyncio
import pytest

from ed_bot.cockpit.models import WatcherEvent, UserCommand, DraftPayload, ActionResult
from ed_bot.cockpit.loop import CockpitLoop
from ed_bot.cockpit.watcher import poll_once


@pytest.mark.anyio
async def test_event_to_post_round_trip():
    q: asyncio.Queue = asyncio.Queue()

    async def fetch_events(course_id):
        return [WatcherEvent(kind="new_thread", thread_id=8100207, number=207,
                             title="Figure 1 graph",
                             category="Project 1 | Martingale", url="u")]

    async def draft_fn(*, number, **kw):
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question="q", body="clean answer", confidence="HIGH")

    async def post_fn(*, number, body, post_kind, target_comment_id):
        return ActionResult(thread_id=8100000 + number, ok=True, posted_id=42,
                            accepted=True, message="ok")

    async def is_answered_fn(number):
        return False

    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=draft_fn,
                       emit=lambda m: None, post_fn=post_fn,
                       is_answered_fn=is_answered_fn)

    # 1. Watcher polls -> event on queue.
    await poll_once(course_id=98559, queue=q, fetch_events=fetch_events)
    # 2. Consumer drains the queue and routes to the loop.
    ev = await q.get()
    await loop.handle(ev)
    # 3. Auto-draft completed.
    assert loop.queue_item(207).draft_state == "ready"
    # 4. Human approves -> posts.
    res = await loop.handle(UserCommand(intent="approve", thread=207))
    assert res.ok and res.accepted
    assert loop.queue_item(207).status == "posted"
```

- [ ] **Step 2: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_headless_e2e.py -q`
Expected: PASS (1 passed).

- [ ] **Step 3: Run the whole cockpit suite**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/ -q`
Expected: all green (default-deselected live test still skipped).

- [ ] **Step 4: Commit**

```bash
git add tests/cockpit/test_headless_e2e.py
git commit -m "test(cockpit): headless end-to-end event-to-post round trip"
```

---

## Task 10: Spec addendum — record the architecture deviation

**Files:**
- Modify: `docs/superpowers/specs/2026-05-31-ed-cockpit-tui-design.md`

- [ ] **Step 1: Append an addendum section**

Add to the end of the spec:

```markdown
## Addendum (2026-05-31, from Plan 2): per-task structured calls

The original "single long-lived agent conversation" framing is refined in
implementation. The Claude Agent SDK exposes structured output (`output_format`)
only at call construction, with no documented per-turn schema switch. So each
agent task is ONE `query()` call with its own `output_format` (classify → draft
→ post), and cross-turn "conversation" is reconstructed by the cockpit (UI
transcript state), not held in one SDK session. Same user-facing behavior;
better SDK fit; avoids stale-context bugs since each task fetches fresh.

The agent session is configured with `system_prompt={"type":"preset","preset":
"claude_code", "append": <hard guardrail+humanizer restatement>}` and
`setting_sources=["project"]` so CLAUDE.md, skills, and guardrails govern the
agent — the configuration the Plan 1 spike was missing. Because the human
reviews every draft before posting, guardrail handling is advisory (a
non-blocking `guardrail_warnings` list), not a hard gate.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-05-31-ed-cockpit-tui-design.md
git commit -m "docs(cockpit): record per-task structured-call architecture decision"
```

---

## Done criteria

- `cockpit.config`, `cockpit.guardrail_scan`, `cockpit.agent`, `cockpit.loop`,
  `cockpit.watcher` all exist and are unit-tested with injected SDK/post/fetch.
- The agent is configured correctly (claude_code preset + setting_sources +
  ed-dir cwd) — the spike's misconfiguration is fixed.
- The headless e2e test proves event → auto-draft → approve → post with no
  network.
- `DraftPayload` carries advisory `guardrail_warnings`; staleness re-check
  guards posting.
- The whole cockpit suite is green; the live SDK test remains `-m live`.
- The spec records the per-task-call architecture decision.

## Deferred to Plan 3 (Textual UI)

- Wiring `emit` to Textual widgets; the chat transcript; hotkeys; modals
  (batch/canned); the alert banner; rendering `guardrail_warnings` as an inline
  advisory.
- Natural-language → `UserCommand` mapping for the chat input (the loop already
  accepts `UserCommand`; the parser that turns typed text into one lives with
  the UI).
- A real `fetch_events` that wraps the sync ed-api client via
  `asyncio.to_thread`, and a real `post_fn`/`is_answered_fn` doing the same.
- Graduation TODOs from the spike findings (typed exception hierarchy, tighten
  the SdkQuery Protocol, top-level anyio config).
```
