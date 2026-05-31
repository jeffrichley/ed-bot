# Cockpit Plan 1 — SDK Spike + Pydantic Models — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the typed Pydantic contract for the cockpit, and prove the Claude Agent SDK can run this project's existing skills and return a schema-valid, humanized `DraftPayload` — the riskiest assumption in the whole design — before any UI is built.

**Architecture:** Two deliverables. (1) A `cockpit.models` package: the Pydantic models that form the agent↔UI contract. (2) A spike module + a small live integration test that drives the SDK's `query()` with `output_format={"type":"json_schema", ...}` derived from a model, pointed at this project's `cwd`/skills, and asserts the result is a valid `DraftPayload` whose body is humanized.

**Tech Stack:** Python 3.12, Pydantic v2, `claude-agent-sdk` (Python), pytest. SDK uses the bundled Claude Code CLI auth (the user's Claude Max subscription) — no API key.

This is the first of three plans. Plan 2 (headless agent loop + async watcher) and Plan 3 (Textual cockpit UI) follow once this proves the SDK behaves.

**Spec:** `docs/superpowers/specs/2026-05-31-ed-cockpit-tui-design.md`

---

## File Structure

- `src/ed_bot/cockpit/__init__.py` — new package marker.
- `src/ed_bot/cockpit/models.py` — the Pydantic contract (all inbound/outbound models). One file: these models are small, change together, and are the shared vocabulary.
- `src/ed_bot/cockpit/spike.py` — a thin function `draft_for_event(event, *, cwd, sdk_query=...)` that calls the SDK and returns a `DraftPayload`. Kept tiny and dependency-injectable so it's unit-testable without a live call.
- `tests/cockpit/__init__.py` — test package marker.
- `tests/cockpit/test_models.py` — model validation + the humanized-only invariant.
- `tests/cockpit/test_spike.py` — spike logic with a fake `sdk_query` (no network).
- `tests/cockpit/test_spike_live.py` — one live SDK integration test, marked `@pytest.mark.live` so the normal suite skips it.
- `pyproject.toml` — add `claude-agent-sdk` dep and a `live` pytest marker.

---

## Task 1: Create the cockpit package and dependency

**Files:**
- Create: `src/ed_bot/cockpit/__init__.py`
- Create: `tests/cockpit/__init__.py`
- Modify: `pyproject.toml` (dependencies + pytest markers)

- [ ] **Step 1: Create the package markers**

Create `src/ed_bot/cockpit/__init__.py` with:

```python
"""Cockpit TUI: typed contract, agent bridge, and Textual UI for the EdStem cockpit."""
```

Create `tests/cockpit/__init__.py` as an empty file.

- [ ] **Step 2: Add the SDK dependency and the `live` marker**

In `pyproject.toml`, add `"claude-agent-sdk>=0.1.0"` to the `[project]` `dependencies` list (place it after `"anthropic>=0.40.0"`).

Then add a pytest markers section. Find `[tool.pytest.ini_options]` and add a `markers` entry so it reads:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
markers = [
    "live: hits the real Claude Agent SDK (deselected by default; run with -m live)",
]
```

- [ ] **Step 3: Install the dependency**

Run: `uv sync`
Expected: completes; `claude-agent-sdk` appears installed. (If `uv sync` reports the version constraint is unsatisfiable, relax to the latest available `claude-agent-sdk` and note the resolved version.)

- [ ] **Step 4: Verify the import works**

Run: `.venv/Scripts/python.exe -c "import claude_agent_sdk; from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/__init__.py tests/cockpit/__init__.py pyproject.toml uv.lock
git commit -m "chore(cockpit): scaffold package and add claude-agent-sdk dep"
```

---

## Task 2: The inbound models (UserCommand, WatcherEvent)

**Files:**
- Create: `src/ed_bot/cockpit/models.py`
- Test: `tests/cockpit/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/cockpit/test_models.py`:

```python
"""Tests for the cockpit Pydantic contract."""
import pytest
from pydantic import ValidationError

from ed_bot.cockpit.models import UserCommand, WatcherEvent


def test_user_command_minimal():
    cmd = UserCommand(intent="check_forum")
    assert cmd.intent == "check_forum"
    assert cmd.thread is None
    assert cmd.text is None


def test_user_command_with_thread_and_text():
    cmd = UserCommand(intent="edit", thread=207, text="make it more Socratic")
    assert cmd.thread == 207
    assert cmd.text == "make it more Socratic"


def test_user_command_rejects_unknown_intent():
    with pytest.raises(ValidationError):
        UserCommand(intent="frobnicate")


def test_watcher_event_roundtrip():
    ev = WatcherEvent(
        kind="new_thread",
        thread_id=8104866,
        number=207,
        title="Figure 1 graph",
        category="Project 1 | Martingale",
        url="https://edstem.org/us/courses/98559/discussion/8104866",
    )
    assert ev.number == 207
    assert ev.kind == "new_thread"


def test_watcher_event_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        WatcherEvent(
            kind="meteor_strike",
            thread_id=1, number=1, title="x", category="y", url="z",
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_models.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'ed_bot.cockpit.models'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/ed_bot/cockpit/models.py`:

```python
"""The typed contract between the cockpit UI and the agent.

Every message into the agent and every structured result out of it is one of
these models. Outbound models are returned by the agent via the SDK's
``output_format`` structured-output mechanism, so the UI consumes validated
objects rather than parsing prose.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

# --- Inbound to the agent ---

CommandIntent = Literal[
    "check_forum", "open", "approve", "edit", "reject",
    "flag", "skip", "post_canned", "watcher_ctl", "freeform",
]

EventKind = Literal["new_thread", "followup", "escalation", "error", "recovered"]


class UserCommand(BaseModel):
    """A human action from the cockpit: a hotkey or typed natural language,
    normalized into a single shape. ``freeform`` carries arbitrary chat text
    for the agent to interpret."""

    intent: CommandIntent
    thread: Optional[int] = None
    text: Optional[str] = None


class WatcherEvent(BaseModel):
    """An actionable forum event produced by the watcher task."""

    kind: EventKind
    thread_id: int
    number: int
    title: str
    category: str
    url: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_models.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/models.py tests/cockpit/test_models.py
git commit -m "feat(cockpit): add inbound contract models (UserCommand, WatcherEvent)"
```

---

## Task 3: The outbound models, with the humanized-only invariant

**Files:**
- Modify: `src/ed_bot/cockpit/models.py`
- Test: `tests/cockpit/test_models.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/cockpit/test_models.py`:

```python
from ed_bot.cockpit.models import (
    QueueItem, QueueUpdate, DraftPayload, StatusUpdate, ActionResult, AlertBanner,
)


def test_queue_item_defaults():
    item = QueueItem(
        thread_id=8104866, number=207, title="Figure 1 graph",
        category="Project 1 | Martingale", kind="new_thread",
    )
    assert item.urgency == "normal"
    assert item.draft_state == "none"
    assert item.status == "needs_attention"


def test_queue_update_holds_items():
    upd = QueueUpdate(items=[
        QueueItem(thread_id=1, number=1, title="a", category="c", kind="new_thread"),
    ])
    assert len(upd.items) == 1


def test_draft_payload_is_humanized_only():
    # The contract must NOT carry a raw / pre-humanizer field. The UI can only
    # ever receive the final body. Guard the invariant explicitly.
    fields = set(DraftPayload.model_fields)
    for forbidden in ("raw_body", "raw_draft", "pre_humanizer", "draft_raw"):
        assert forbidden not in fields, f"DraftPayload must not expose {forbidden}"
    assert "body" in fields


def test_draft_payload_roundtrip():
    d = DraftPayload(
        thread_id=8104866, number=207,
        question="How is Figure 1 graded?",
        body="The autograder checks returned values, not the PNG.",
        is_canned=False, project="Project 1 - Martingale",
        guardrails_checked=["martingale"], confidence="HIGH",
        post_kind="answer", target_comment_id=None,
    )
    assert d.confidence == "HIGH"
    assert d.post_kind == "answer"


def test_action_result_failure_shape():
    r = ActionResult(thread_id=1, ok=False, posted_id=None, accepted=False,
                     message="400 Bad Request")
    assert r.ok is False
    assert r.posted_id is None


def test_status_and_alert():
    assert StatusUpdate(line="drafting #207...").line.startswith("drafting")
    a = AlertBanner(thread_id=1, number=166, title="Medical Emergency", text="urgent")
    assert a.number == 166
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_models.py -q`
Expected: FAIL with `ImportError: cannot import name 'QueueItem'`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/ed_bot/cockpit/models.py`:

```python
# --- Outbound from the agent to the UI ---

DraftState = Literal["drafting", "ready", "flagged", "failed", "none"]
ItemStatus = Literal["needs_attention", "posted", "dismissed"]
Urgency = Literal["normal", "high"]
Confidence = Literal["HIGH", "MEDIUM", "LOW"]
PostKind = Literal["answer", "reply"]


class QueueItem(BaseModel):
    """One row in the left-rail queue."""

    thread_id: int
    number: int
    title: str
    category: str
    kind: EventKind
    urgency: Urgency = "normal"
    draft_state: DraftState = "none"
    status: ItemStatus = "needs_attention"


class QueueUpdate(BaseModel):
    """The full set of queue items to reconcile into the rail."""

    items: list[QueueItem]


class DraftPayload(BaseModel):
    """A drafted reply for one thread. ``body`` is ALWAYS the final,
    post-humanizer text. There is deliberately no raw-draft field: the UI must
    never be able to display pre-humanizer content."""

    thread_id: int
    number: int
    question: str
    body: str
    is_canned: bool = False
    project: Optional[str] = None
    guardrails_checked: list[str] = []
    confidence: Confidence = "MEDIUM"
    post_kind: PostKind = "answer"
    target_comment_id: Optional[int] = None


class StatusUpdate(BaseModel):
    """One line for the status bar."""

    line: str


class ActionResult(BaseModel):
    """Outcome of a post/accept action."""

    thread_id: int
    ok: bool
    posted_id: Optional[int] = None
    accepted: bool = False
    message: str = ""


class AlertBanner(BaseModel):
    """An escalation surfaced inline: triggers the header flash + sound."""

    thread_id: int
    number: int
    title: str
    text: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_models.py -q`
Expected: PASS (11 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/models.py tests/cockpit/test_models.py
git commit -m "feat(cockpit): add outbound contract models with humanized-only invariant"
```

---

## Task 4: The spike function (unit-testable, no network)

**Files:**
- Create: `src/ed_bot/cockpit/spike.py`
- Test: `tests/cockpit/test_spike.py`

The spike calls the SDK, but we inject the SDK call so we can unit-test the
logic (prompt construction, schema wiring, result parsing) without a live
request. The real SDK is exercised separately in Task 5.

- [ ] **Step 1: Write the failing test**

Create `tests/cockpit/test_spike.py`:

```python
"""Unit tests for the spike's logic, with a fake SDK query (no network)."""
import pytest

from ed_bot.cockpit.models import WatcherEvent, DraftPayload
from ed_bot.cockpit.spike import draft_for_event


def _event():
    return WatcherEvent(
        kind="new_thread", thread_id=8104866, number=207,
        title="Figure 1 graph", category="Project 1 | Martingale",
        url="https://edstem.org/us/courses/98559/discussion/8104866",
    )


@pytest.mark.anyio
async def test_draft_for_event_returns_validated_payload():
    # Fake the SDK: return a dict matching the DraftPayload schema.
    async def fake_sdk_query(*, prompt, schema, cwd):
        # The function under test must pass us a json-schema dict and a prompt
        # mentioning the thread number.
        assert schema["type"] == "object"
        assert "207" in prompt
        return {
            "thread_id": 8104866, "number": 207,
            "question": "How does Gradescope check our chart output?",
            "body": "The autograder reads the returned values, not the image.",
            "is_canned": False, "project": "Project 1 - Martingale",
            "guardrails_checked": ["martingale"], "confidence": "HIGH",
            "post_kind": "answer", "target_comment_id": None,
        }

    payload = await draft_for_event(_event(), cwd=".", sdk_query=fake_sdk_query)
    assert isinstance(payload, DraftPayload)
    assert payload.number == 207
    assert payload.confidence == "HIGH"


@pytest.mark.anyio
async def test_draft_for_event_raises_on_schema_violation():
    async def bad_sdk_query(*, prompt, schema, cwd):
        return {"number": 207}  # missing required fields

    with pytest.raises(Exception):
        await draft_for_event(_event(), cwd=".", sdk_query=bad_sdk_query)
```

Note: this project's existing tests are all synchronous — there is no async
pytest support yet. Task 4 Step 4 adds it (an `anyio_backend` fixture). This
test file therefore depends on Step 4 being done; if you run it before Step 4
you will get an "unknown marker: anyio" error, which Step 4 resolves.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_spike.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'ed_bot.cockpit.spike'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/ed_bot/cockpit/spike.py`:

```python
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
        setting_sources=["project"],   # load .claude (CLAUDE.md, skills)
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
```

- [ ] **Step 4: Ensure async tests can run**

Check `tests/conftest.py` for existing async support. If `@pytest.mark.anyio`
is not recognized (error: "unknown marker"), add an anyio backend fixture to
`tests/cockpit/__init__.py`'s sibling `tests/cockpit/conftest.py`:

Create `tests/cockpit/conftest.py`:

```python
import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"
```

If `anyio` is not installed, run `uv add --dev anyio` and re-sync.

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_spike.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add src/ed_bot/cockpit/spike.py tests/cockpit/test_spike.py tests/cockpit/conftest.py
git commit -m "feat(cockpit): add SDK spike with injectable query (unit-tested)"
```

---

## Task 5: The live SDK integration test (the actual de-risking)

**Files:**
- Create: `tests/cockpit/test_spike_live.py`

This is the test that proves the assumption. It is `@pytest.mark.live` so the
normal suite skips it; you run it explicitly. It uses a REAL thread that is
known to exist (#207, "Figure 1 graph", id 8104866 — already answered, so the
agent will draft against real content without us posting anything).

- [ ] **Step 1: Write the live test**

Create `tests/cockpit/test_spike_live.py`:

```python
"""Live SDK integration test. Deselected by default; run with:

    .venv/Scripts/python.exe -m pytest tests/cockpit/test_spike_live.py -m live -s

Proves the Claude Agent SDK can run this project's skills and return a
schema-valid, humanized DraftPayload. Does NOT post anything to EdStem.
"""
import pytest

from ed_bot.cockpit.models import WatcherEvent, DraftPayload
from ed_bot.cockpit.spike import draft_for_event


@pytest.mark.live
@pytest.mark.anyio
async def test_live_draft_for_real_thread():
    event = WatcherEvent(
        kind="new_thread", thread_id=8104866, number=207,
        title="Figure 1 graph", category="Project 1 | Martingale",
        url="https://edstem.org/us/courses/98559/discussion/8104866",
    )

    payload = await draft_for_event(event, cwd=".")

    # It must be a valid DraftPayload (model_validate already ran inside).
    assert isinstance(payload, DraftPayload)
    assert payload.number == 207
    assert payload.body.strip(), "body must be non-empty"

    # Humanizer signature: the project bans em dashes. A humanized answer must
    # not contain one. This is a cheap proxy that the humanizer ran.
    assert "—" not in payload.body, "em dash present — humanizer likely skipped"

    # Print for human eyeballing during the spike.
    print("\n--- LIVE DRAFT ---\n", payload.model_dump_json(indent=2))
```

- [ ] **Step 2: Confirm the normal suite skips it**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit -q`
Expected: PASS, and the live test is deselected (output shows "deselected" or it simply does not run). It must NOT make a network call here.

- [ ] **Step 3: Run the live test explicitly**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_spike_live.py -m live -s`
Expected: PASS. The printed `--- LIVE DRAFT ---` shows a real, humanized answer to #207 with guardrails listed and no em dash.

**If this fails**, that is the whole point of the spike — capture the failure
mode (auth, structured-output mismatch, skills not loading, em dash present)
and report it before proceeding to Plan 2. Likely fixes to investigate:
- `setting_sources=["project"]` not loading `.claude` → try `add_dirs=[".claude"]` or verify the CLAUDE.md is found via `cwd`.
- `skills="all"` not picking up `.claude/skills` → confirm skill discovery path.
- Structured output empty → confirm the installed SDK version exposes
  `ResultMessage.structured_output` (it may differ by version; adjust parsing).

- [ ] **Step 4: Commit**

```bash
git add tests/cockpit/test_spike_live.py
git commit -m "test(cockpit): add live SDK integration test for the draft spike"
```

---

## Task 6: Record spike findings

**Files:**
- Create: `docs/superpowers/specs/2026-05-31-cockpit-sdk-spike-findings.md`

- [ ] **Step 1: Write the findings doc**

Capture, in prose: whether the live test passed; the real shape of the SDK
calls that worked (exact `ClaudeAgentOptions` fields used); how skills/CLAUDE.md
loading actually resolved; the installed `claude-agent-sdk` version; and any
deviations from this plan's assumptions. Plans 2 and 3 will be written against
THIS file, not against guesses.

```markdown
# Cockpit SDK Spike — Findings (2026-05-31)

- claude-agent-sdk version: <fill in>
- Live test result: <pass/fail + details>
- Working ClaudeAgentOptions: <exact fields>
- Skills / CLAUDE.md loading: <what worked>
- structured_output access path: <ResultMessage.structured_output or other>
- Humanizer verified in output: <yes/no, evidence>
- Surprises / deviations: <...>
- Implications for Plan 2: <...>
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-05-31-cockpit-sdk-spike-findings.md
git commit -m "docs(cockpit): record SDK spike findings"
```

---

## Done criteria

- `cockpit.models` exists with the full contract; the humanized-only invariant
  is enforced by a test.
- The spike logic is unit-tested with an injected SDK.
- The live test either passes (SDK proven) or its failure mode is documented in
  the findings doc.
- The normal `pytest` run is green and does not hit the network; the live test
  runs only under `-m live`.
- Findings are recorded so Plans 2 and 3 build on verified API behavior.
