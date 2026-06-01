# Cockpit Plan 3 — Textual UI (Layout A) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Textual cockpit UI (Layout A) on top of the Plan 2 headless loop: a queue rail, a draft viewer, a chat/command input, a status bar, one-key actions, and an escalation banner — wired to `CockpitLoop` so forum events auto-draft and the human reviews and posts.

**Architecture:** A Textual `App`. The headless `CockpitLoop` runs in the same asyncio event loop. The loop's `emit` callback wraps each Pydantic result in a custom Textual `Message` (`LoopEmission`) and `post_message`s it; one handler routes by payload type to update widgets. Keystrokes and hotkeys turn into `UserCommand`s handed to the loop via an `@work()` async worker. No threads, no IPC — everything shares the event loop.

**Tech Stack:** Python 3.12, Textual, Pydantic v2, the existing `ed_bot.cockpit` package (loop, models, agent, watcher, config), pytest + anyio + Textual's `run_test`/`Pilot`.

**Spec:** `docs/superpowers/specs/2026-05-31-ed-cockpit-tui-design.md`
**Prior plans:** Plan 1 (`...-plan-1-sdk-spike-and-models.md`), Plan 2 (`...-plan-2-headless-agent-loop.md`) — both merged.

---

## Key facts the implementer needs

- The headless loop already exists: `from ed_bot.cockpit.loop import CockpitLoop`.
  Construct with `CockpitLoop(*, cwd, course_id, draft_fn, emit, post_fn=None,
  is_answered_fn=None)`. Drive it with `await loop.handle(msg)` where `msg` is a
  `WatcherEvent` or `UserCommand`. Read state via `loop.queue_item(number)` →
  `QueueItem | None` and `loop.draft(number)` → `DraftPayload | None`.
- The loop calls its `emit(obj)` callback (sync) with one of: `QueueUpdate`,
  `StatusUpdate`, `ActionResult`. (`DraftPayload`/`AlertBanner` are surfaced via
  loop state and the queue; the UI reads `loop.draft()` when an item is
  selected.) Models are in `ed_bot.cockpit.models`.
- Textual is NOT yet a dependency. Task 1 adds it.
- Textual app testing uses `async with app.run_test() as pilot:` then
  `await pilot.press("a")`, `await pilot.pause()`, and querying widgets with
  `app.query_one(...)`. Tests are `@pytest.mark.anyio` async (anyio backend
  fixture already exists in `tests/cockpit/conftest.py`).
- Both the loop and Textual run on one asyncio loop, so UI updates happen via
  `post_message` from the `emit` callback — never `call_from_thread`.

---

## File Structure

- `src/ed_bot/cockpit/messages.py` — the custom Textual `Message` types that
  carry loop emissions into the app.
- `src/ed_bot/cockpit/widgets.py` — the leaf widgets: `QueueRail`,
  `DraftViewer`, `StatusBar`, `AlertBanner` (display-only, fed by the app).
- `src/ed_bot/cockpit/command_parser.py` — turns typed chat text into a
  `UserCommand`.
- `src/ed_bot/cockpit/app.py` — the `CockpitApp`: composes Layout A, owns the
  `CockpitLoop`, routes `LoopEmission` messages, handles hotkeys + chat input.
- `src/ed_bot/cockpit/app.tcss` — the Textual CSS for Layout A.
- `src/ed_bot/cockpit/__main__.py` — entry point that wires the real watcher /
  agent / ed-api fns and runs the app. (Thin; not heavily tested.)
- Tests mirror each under `tests/cockpit/`.

---

## Task 1: Add Textual and scaffold the UI module surface

**Files:**
- Modify: `pyproject.toml`
- Create: `src/ed_bot/cockpit/messages.py`
- Test: `tests/cockpit/test_messages.py`

- [ ] **Step 1: Add the dependency**

In `pyproject.toml` `[project]` `dependencies`, add `"textual>=0.60"` after the
`"rich>=13.0.0"` line (Textual builds on rich, already present).

- [ ] **Step 2: Install**

Run: `uv sync`
Expected: completes; `textual` installed. (If `>=0.60` is unsatisfiable, run
`uv add textual` and note the resolved version.)

- [ ] **Step 3: Write the failing test**

Create `tests/cockpit/test_messages.py`:

```python
"""Tests for the Textual message wrappers carrying loop emissions."""
from ed_bot.cockpit.models import QueueUpdate, StatusUpdate
from ed_bot.cockpit.messages import LoopEmission


def test_loop_emission_carries_payload():
    payload = StatusUpdate(line="drafting #207...")
    msg = LoopEmission(payload)
    assert msg.payload is payload


def test_loop_emission_accepts_queue_update():
    payload = QueueUpdate(items=[])
    msg = LoopEmission(payload)
    assert isinstance(msg.payload, QueueUpdate)
```

- [ ] **Step 4: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_messages.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'ed_bot.cockpit.messages'`.

- [ ] **Step 5: Implement**

Create `src/ed_bot/cockpit/messages.py`:

```python
"""Textual Message wrappers that carry headless-loop emissions into the app.

The loop's ``emit`` callback is sync and must not touch widgets directly. It
wraps each Pydantic result in a ``LoopEmission`` and posts it; the app routes by
``payload`` type. This keeps the loop fully decoupled from the widget tree."""
from __future__ import annotations

from typing import Any

from textual.message import Message


class LoopEmission(Message):
    """One emission from the CockpitLoop (a QueueUpdate / StatusUpdate /
    ActionResult), delivered to the app as a Textual message."""

    def __init__(self, payload: Any) -> None:
        super().__init__()
        self.payload = payload
```

- [ ] **Step 6: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_messages.py -q`
Expected: PASS (2 passed).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock src/ed_bot/cockpit/messages.py tests/cockpit/test_messages.py
git commit -m "feat(cockpit): add Textual dep and LoopEmission message wrapper"
```

---

## Task 2: The command parser (chat text → UserCommand)

**Files:**
- Create: `src/ed_bot/cockpit/command_parser.py`
- Test: `tests/cockpit/test_command_parser.py`

- [ ] **Step 1: Write the failing test**

Create `tests/cockpit/test_command_parser.py`:

```python
"""Tests for parsing typed chat text into a UserCommand."""
from ed_bot.cockpit.command_parser import parse_command
from ed_bot.cockpit.models import UserCommand


def test_check_forum():
    cmd = parse_command("check the forum")
    assert cmd.intent == "check_forum"


def test_open_with_number():
    cmd = parse_command("answer 207")
    assert cmd.intent == "open"
    assert cmd.thread == 207


def test_open_with_hash_number():
    cmd = parse_command("open #212")
    assert cmd.intent == "open"
    assert cmd.thread == 212


def test_post_it_is_approve():
    assert parse_command("post it").intent == "approve"


def test_edit_carries_text():
    cmd = parse_command("make it more Socratic", active_thread=207)
    assert cmd.intent == "edit"
    assert cmd.thread == 207
    assert cmd.text == "make it more Socratic"


def test_unknown_is_freeform():
    cmd = parse_command("what's the weather", active_thread=None)
    assert cmd.intent == "freeform"
    assert cmd.text == "what's the weather"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_command_parser.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Create `src/ed_bot/cockpit/command_parser.py`:

```python
"""Turn typed chat text into a UserCommand.

A small, deterministic parser for the common verbs; anything unrecognized
becomes a ``freeform`` command for the agent to interpret. The optional
``active_thread`` lets bare commands ("post it", "make it more Socratic")
target the thread currently open in the draft viewer."""
from __future__ import annotations

import re
from typing import Optional

from ed_bot.cockpit.models import UserCommand

_NUM = re.compile(r"#?(\d{1,6})")


def _first_number(text: str) -> Optional[int]:
    m = _NUM.search(text)
    return int(m.group(1)) if m else None


def parse_command(text: str, *, active_thread: Optional[int] = None) -> UserCommand:
    t = text.strip()
    low = t.lower()

    if "check" in low and "forum" in low:
        return UserCommand(intent="check_forum")

    if low.startswith(("answer", "open", "show", "draft")):
        return UserCommand(intent="open", thread=_first_number(t) or active_thread)

    if low in ("post it", "post", "approve", "send it", "ship it"):
        return UserCommand(intent="approve", thread=active_thread)

    if low in ("reject", "discard"):
        return UserCommand(intent="reject", thread=active_thread)

    if low in ("flag", "needs human", "flag for human"):
        return UserCommand(intent="flag", thread=active_thread)

    if low in ("skip", "next"):
        return UserCommand(intent="skip", thread=active_thread)

    if low.startswith(("make it", "edit", "revise", "redo", "more ", "less ")):
        return UserCommand(intent="edit", thread=active_thread, text=t)

    return UserCommand(intent="freeform", thread=active_thread, text=t)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_command_parser.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/command_parser.py tests/cockpit/test_command_parser.py
git commit -m "feat(cockpit): parse chat text into UserCommand"
```

---

## Task 3: The display widgets

**Files:**
- Create: `src/ed_bot/cockpit/widgets.py`
- Test: `tests/cockpit/test_widgets.py`

Display-only widgets with pure render helpers so they're unit-testable without
mounting a full app. Each has a classmethod/staticmethod that turns a model into
display text, plus the widget that uses it.

- [ ] **Step 1: Write the failing test**

Create `tests/cockpit/test_widgets.py`:

```python
"""Tests for the cockpit display widgets' pure render helpers."""
from ed_bot.cockpit.models import QueueItem, DraftPayload
from ed_bot.cockpit.widgets import render_queue_line, render_draft


def _item(**over):
    base = dict(thread_id=8100207, number=207, title="Figure 1 graph",
                category="Project 1 | Martingale", kind="new_thread",
                urgency="normal", draft_state="ready", status="needs_attention")
    base.update(over)
    return QueueItem(**base)


def test_render_queue_line_shows_number_and_title():
    line = render_queue_line(_item())
    assert "207" in line
    assert "Figure 1 graph" in line


def test_render_queue_line_marks_escalation():
    line = render_queue_line(_item(kind="escalation", urgency="high"))
    assert "!" in line  # escalation marker


def test_render_queue_line_shows_drafting_state():
    line = render_queue_line(_item(draft_state="drafting"))
    assert "drafting" in line.lower() or "..." in line


def test_render_draft_includes_question_body_and_confidence():
    d = DraftPayload(thread_id=8100207, number=207,
                     question="How is Figure 1 graded?",
                     body="The autograder checks returned values.",
                     confidence="HIGH", guardrails_checked=["martingale"])
    text = render_draft(d)
    assert "How is Figure 1 graded?" in text
    assert "The autograder checks returned values." in text
    assert "HIGH" in text


def test_render_draft_shows_guardrail_warnings():
    d = DraftPayload(thread_id=1, number=1, question="q", body="b",
                     guardrail_warnings=["possible Never-Reveal leak: 18/38"])
    text = render_draft(d)
    assert "18/38" in text
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_widgets.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Create `src/ed_bot/cockpit/widgets.py`:

```python
"""Cockpit display widgets and their pure render helpers (Layout A).

The render helpers are module functions so they can be unit-tested without
mounting an app. The widgets are thin wrappers the app updates."""
from __future__ import annotations

from textual.widgets import Static

from ed_bot.cockpit.models import QueueItem, DraftPayload


def render_queue_line(item: QueueItem) -> str:
    """One line for the queue rail."""
    mark = "!" if item.kind == "escalation" else " "
    state = {
        "drafting": "drafting...",
        "ready": "ready",
        "flagged": "flagged",
        "failed": "failed",
        "none": "",
    }.get(item.draft_state, "")
    posted = " (posted)" if item.status == "posted" else ""
    return f"{mark} #{item.number} {item.title} [{state}]{posted}".rstrip()


def render_draft(d: DraftPayload) -> str:
    """The center-panel text for a selected draft."""
    lines = [
        f"#{d.number}  ({d.project or 'unknown project'})  conf: {d.confidence}",
        "",
        f"Q: {d.question}",
        "",
        d.body,
    ]
    if d.guardrails_checked:
        lines += ["", f"guardrails checked: {', '.join(d.guardrails_checked)}"]
    if d.guardrail_warnings:
        lines += ["", "ADVISORY:"]
        lines += [f"  - {w}" for w in d.guardrail_warnings]
    lines += ["", "[a]pprove  [e]dit  [r]eject  [f]lag  [s]kip"]
    return "\n".join(lines)


class QueueRail(Static):
    """Left rail: the list of actionable threads."""

    def show(self, items: list[QueueItem]) -> None:
        if not items:
            self.update("(queue empty)")
            return
        self.update("\n".join(render_queue_line(i) for i in items))


class DraftViewer(Static):
    """Center panel: the selected thread's draft."""

    def show(self, draft: DraftPayload | None) -> None:
        self.update(render_draft(draft) if draft else "(select a thread)")


class StatusBar(Static):
    """One-line status of what the agent is doing."""

    def show(self, line: str) -> None:
        self.update(line)


class AlertBanner(Static):
    """Header flash for escalations. Hidden unless an alert is active."""

    def flash(self, text: str) -> None:
        self.update(f"  {text}  ")
        self.styles.display = "block"

    def clear_alert(self) -> None:
        self.update("")
        self.styles.display = "none"
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_widgets.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/widgets.py tests/cockpit/test_widgets.py
git commit -m "feat(cockpit): display widgets with pure render helpers"
```

---

## Task 4: The CockpitApp shell — compose Layout A + emit routing

**Files:**
- Create: `src/ed_bot/cockpit/app.py`
- Create: `src/ed_bot/cockpit/app.tcss`
- Test: `tests/cockpit/test_app_compose.py`

Build the app skeleton: it composes Layout A, owns a `CockpitLoop` (with injected
fns), sets the loop's `emit` to post `LoopEmission` messages, and routes them to
widgets. Hotkeys/chat come in Task 5.

- [ ] **Step 1: Write the failing test**

Create `tests/cockpit/test_app_compose.py`:

```python
"""Tests that the app composes Layout A and routes loop emissions to widgets."""
import pytest

from ed_bot.cockpit.app import CockpitApp
from ed_bot.cockpit.widgets import QueueRail, DraftViewer, StatusBar
from ed_bot.cockpit.models import WatcherEvent, DraftPayload


def _make_app():
    async def draft_fn(*, number, **kw):
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question="q", body="clean body", confidence="HIGH")

    return CockpitApp(cwd=".", course_id=98559, draft_fn=draft_fn,
                      post_fn=None, is_answered_fn=None,
                      fetch_events=None)


@pytest.mark.anyio
async def test_app_mounts_core_widgets():
    app = _make_app()
    async with app.run_test() as pilot:
        assert app.query_one(QueueRail)
        assert app.query_one(DraftViewer)
        assert app.query_one(StatusBar)


@pytest.mark.anyio
async def test_event_autodrafts_and_queue_rail_updates():
    app = _make_app()
    async with app.run_test() as pilot:
        await app.inject_event(WatcherEvent(
            kind="new_thread", thread_id=8100207, number=207,
            title="Figure 1 graph", category="Project 1 | Martingale", url="u"))
        await pilot.pause()
        rail = app.query_one(QueueRail)
        assert "207" in str(rail.renderable)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_app_compose.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'ed_bot.cockpit.app'`.

- [ ] **Step 3: Implement the CSS**

Create `src/ed_bot/cockpit/app.tcss`:

```css
Screen {
    layout: vertical;
}

#alert {
    display: none;
    background: $error;
    color: $text;
    height: 1;
    content-align: center middle;
}

#body {
    height: 1fr;
}

#queue {
    width: 38%;
    border: solid $primary;
}

#draft {
    width: 1fr;
    border: solid $primary;
}

#status {
    height: 1;
    background: $panel;
    color: $text-muted;
}

#chat {
    height: 3;
}
```

- [ ] **Step 4: Implement the app**

Create `src/ed_bot/cockpit/app.py`:

```python
"""The CockpitApp: Layout A Textual UI over the headless CockpitLoop.

The loop runs in the app's asyncio loop. Its ``emit`` callback wraps each
result in a ``LoopEmission`` and posts it; ``on_loop_emission`` routes by type
to the widgets. Forum events and user commands are fed to the loop via async
workers. (Hotkeys and chat input arrive in the next task.)"""
from __future__ import annotations

from typing import Any, Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Input
from textual.work import work

from ed_bot.cockpit.loop import CockpitLoop
from ed_bot.cockpit.messages import LoopEmission
from ed_bot.cockpit.models import (
    WatcherEvent, UserCommand, QueueUpdate, StatusUpdate, ActionResult,
)
from ed_bot.cockpit.widgets import QueueRail, DraftViewer, StatusBar, AlertBanner


class CockpitApp(App):
    CSS_PATH = "app.tcss"

    def __init__(self, *, cwd: str, course_id: int, draft_fn,
                 post_fn=None, is_answered_fn=None, fetch_events=None) -> None:
        super().__init__()
        self._fetch_events = fetch_events
        self._active_thread: Optional[int] = None
        self.loop = CockpitLoop(
            cwd=cwd, course_id=course_id, draft_fn=draft_fn,
            emit=self._emit, post_fn=post_fn, is_answered_fn=is_answered_fn,
        )

    def compose(self) -> ComposeResult:
        yield Header()
        yield AlertBanner(id="alert")
        with Horizontal(id="body"):
            yield QueueRail(id="queue")
            yield DraftViewer(id="draft")
        yield StatusBar(id="status")
        yield Input(placeholder="type a command (e.g. 'post it')", id="chat")
        yield Footer()

    # --- loop -> UI bridge ---
    def _emit(self, payload: Any) -> None:
        """Sync callback handed to the loop; never touches widgets directly."""
        self.post_message(LoopEmission(payload))

    def on_loop_emission(self, message: LoopEmission) -> None:
        payload = message.payload
        if isinstance(payload, QueueUpdate):
            self.query_one(QueueRail).show(payload.items)
        elif isinstance(payload, StatusUpdate):
            self.query_one(StatusBar).show(payload.line)
        elif isinstance(payload, ActionResult):
            ok = "posted" if payload.ok else f"not posted: {payload.message}"
            self.query_one(StatusBar).show(ok)

    # --- feeding the loop ---
    @work()
    async def inject_event(self, event: WatcherEvent) -> None:
        await self.loop.handle(event)

    @work()
    async def inject_command(self, cmd: UserCommand) -> None:
        result = await self.loop.handle(cmd)
        if isinstance(result, type(None)):
            return
        # An 'open' returns a DraftPayload; show it.
        from ed_bot.cockpit.models import DraftPayload
        if isinstance(result, DraftPayload):
            self._active_thread = result.number
            self.query_one(DraftViewer).show(result)
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_app_compose.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add src/ed_bot/cockpit/app.py src/ed_bot/cockpit/app.tcss tests/cockpit/test_app_compose.py
git commit -m "feat(cockpit): CockpitApp shell with Layout A and emit routing"
```

---

## Task 5: Chat input + hotkeys

**Files:**
- Modify: `src/ed_bot/cockpit/app.py`
- Test: `tests/cockpit/test_app_interaction.py`

Wire the chat `Input` (submit → parse → command) and the one-key actions
(a/e/r/f/s) via `BINDINGS`. Selecting a thread by typing "open N" already works
from Task 4; hotkeys act on the active thread.

- [ ] **Step 1: Write the failing test**

Create `tests/cockpit/test_app_interaction.py`:

```python
"""Tests for chat input and hotkeys driving the loop."""
import pytest

from ed_bot.cockpit.app import CockpitApp
from ed_bot.cockpit.widgets import DraftViewer
from ed_bot.cockpit.models import WatcherEvent, DraftPayload, ActionResult


def _make_app(posted):
    async def draft_fn(*, number, **kw):
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question="q", body="clean body", confidence="HIGH")

    async def post_fn(*, number, body, post_kind, target_comment_id):
        posted.append(number)
        return ActionResult(thread_id=8100000 + number, ok=True, posted_id=9,
                            accepted=True, message="ok")

    async def is_answered_fn(number):
        return False

    return CockpitApp(cwd=".", course_id=98559, draft_fn=draft_fn,
                      post_fn=post_fn, is_answered_fn=is_answered_fn,
                      fetch_events=None)


@pytest.mark.anyio
async def test_typing_open_then_chat_post_it_posts():
    posted = []
    app = _make_app(posted)
    async with app.run_test() as pilot:
        await app.inject_event(WatcherEvent(
            kind="new_thread", thread_id=8100207, number=207,
            title="Figure 1 graph", category="Project 1 | Martingale", url="u"))
        await pilot.pause()
        # Type "open 207" into chat and submit.
        chat = app.query_one("#chat")
        chat.value = "open 207"
        await pilot.press("enter")
        await pilot.pause()
        assert "clean body" in str(app.query_one(DraftViewer).renderable)
        # Now "post it".
        chat.value = "post it"
        await pilot.press("enter")
        await pilot.pause()
        assert posted == [207]


@pytest.mark.anyio
async def test_hotkey_a_approves_active_thread():
    posted = []
    app = _make_app(posted)
    async with app.run_test() as pilot:
        await app.inject_event(WatcherEvent(
            kind="new_thread", thread_id=8100207, number=207,
            title="t", category="Project 1 | Martingale", url="u"))
        await pilot.pause()
        # Open via chat, then approve via hotkey.
        chat = app.query_one("#chat")
        chat.value = "open 207"
        await pilot.press("enter")
        await pilot.pause()
        # Move focus off the input so the hotkey registers, then press 'a'.
        app.set_focus(None)
        await pilot.press("a")
        await pilot.pause()
        assert posted == [207]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_app_interaction.py -q`
Expected: FAIL — the chat submit handler and hotkey actions don't exist yet
(no posting happens; assertions fail).

- [ ] **Step 3: Implement — add to `src/ed_bot/cockpit/app.py`**

Add the `BINDINGS` and the import for the parser near the top of the class /
module. Add `from ed_bot.cockpit.command_parser import parse_command` to the
imports. Add this class attribute inside `CockpitApp` (above `__init__`):

```python
    BINDINGS = [
        ("a", "act('approve')", "approve"),
        ("e", "act('edit')", "edit"),
        ("r", "act('reject')", "reject"),
        ("f", "act('flag')", "flag"),
        ("s", "act('skip')", "skip"),
    ]
```

Add these methods to `CockpitApp`:

```python
    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        cmd = parse_command(text, active_thread=self._active_thread)
        self.inject_command(cmd)

    def action_act(self, intent: str) -> None:
        if self._active_thread is None:
            self.query_one(StatusBar).show("no active thread")
            return
        self.inject_command(UserCommand(intent=intent, thread=self._active_thread))
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_app_interaction.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the whole cockpit suite**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/ -q`
Expected: all green (live SDK test deselected).

- [ ] **Step 6: Commit**

```bash
git add src/ed_bot/cockpit/app.py tests/cockpit/test_app_interaction.py
git commit -m "feat(cockpit): chat input and one-key actions"
```

---

## Task 6: Escalation alert banner routing

**Files:**
- Modify: `src/ed_bot/cockpit/app.py`
- Test: `tests/cockpit/test_app_alert.py`

When a `QueueUpdate` includes a high-urgency escalation item that is new, flash
the alert banner. Keep it simple: flash on the presence of any escalation item
in `needs_attention` status; clear when none remain.

- [ ] **Step 1: Write the failing test**

Create `tests/cockpit/test_app_alert.py`:

```python
"""Tests for the escalation alert banner."""
import pytest

from ed_bot.cockpit.app import CockpitApp
from ed_bot.cockpit.widgets import AlertBanner
from ed_bot.cockpit.models import WatcherEvent, DraftPayload


def _make_app():
    async def draft_fn(*, number, **kw):
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question="q", body="b", confidence="HIGH")
    return CockpitApp(cwd=".", course_id=98559, draft_fn=draft_fn,
                      post_fn=None, is_answered_fn=None, fetch_events=None)


@pytest.mark.anyio
async def test_escalation_flashes_alert_banner():
    app = _make_app()
    async with app.run_test() as pilot:
        await app.inject_event(WatcherEvent(
            kind="escalation", thread_id=8100166, number=166,
            title="Medical Emergency URGENT", category="Project 1 | Martingale",
            url="u"))
        await pilot.pause()
        banner = app.query_one(AlertBanner)
        assert banner.styles.display.name == "block"
        assert "166" in str(banner.renderable) or "Medical" in str(banner.renderable)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_app_alert.py -q`
Expected: FAIL — the banner stays hidden (display none); assertion fails.

- [ ] **Step 3: Implement — extend `on_loop_emission` in `src/ed_bot/cockpit/app.py`**

Replace the `QueueUpdate` branch of `on_loop_emission` with one that also drives
the banner:

```python
        if isinstance(payload, QueueUpdate):
            self.query_one(QueueRail).show(payload.items)
            escalations = [
                i for i in payload.items
                if i.kind == "escalation" and i.status == "needs_attention"
            ]
            banner = self.query_one(AlertBanner)
            if escalations:
                top = escalations[0]
                banner.flash(f"ESCALATION #{top.number}: {top.title}")
            else:
                banner.clear_alert()
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_app_alert.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/app.py tests/cockpit/test_app_alert.py
git commit -m "feat(cockpit): flash alert banner on escalation"
```

---

## Task 7: The entry point that wires the real backends

**Files:**
- Create: `src/ed_bot/cockpit/__main__.py`
- Test: `tests/cockpit/test_main_wiring.py`

A thin module that builds the real `fetch_events` (wrapping the sync ed-api
client via `asyncio.to_thread`), the real `draft_fn` (the agent), the real
`post_fn`/`is_answered_fn`, and runs the app. We unit-test only the wiring
helpers (the agent/ed-api calls themselves are injected/mocked), not a live run.

- [ ] **Step 1: Write the failing test**

Create `tests/cockpit/test_main_wiring.py`:

```python
"""Tests for the entry-point wiring helpers (no live app run)."""
import pytest

from ed_bot.cockpit.__main__ import build_draft_fn


@pytest.mark.anyio
async def test_build_draft_fn_delegates_to_agent():
    calls = {}

    async def fake_draft_thread(*, number, cwd, course_id):
        calls["number"] = number
        from ed_bot.cockpit.models import DraftPayload
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question="q", body="b", confidence="HIGH")

    draft_fn = build_draft_fn(cwd="/ed", draft_thread=fake_draft_thread)
    payload = await draft_fn(number=207, cwd="/ignored", course_id=98559)
    assert calls["number"] == 207
    assert payload.number == 207
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_main_wiring.py -q`
Expected: FAIL with `ImportError` (no `build_draft_fn`).

- [ ] **Step 3: Implement**

Create `src/ed_bot/cockpit/__main__.py`:

```python
"""Entry point: wire the real backends and run the cockpit.

Run with:  python -m ed_bot.cockpit

The wiring helpers are split out and injectable so they can be unit-tested
without a live app run or network."""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from ed_bot.cockpit.agent import draft_thread as _agent_draft_thread
from ed_bot.cockpit.config import ed_working_dir, resolve_course_id
from ed_bot.cockpit.models import DraftPayload


def build_draft_fn(*, cwd: str, draft_thread=_agent_draft_thread):
    """The loop's draft_fn: always run the agent from the ed working dir so its
    tools (ed-api token, ~/.ed-bot) resolve, regardless of the number's cwd."""
    async def draft_fn(*, number: int, cwd: str = cwd, course_id: int) -> DraftPayload:
        return await draft_thread(number=number, cwd=cwd, course_id=course_id)
    return draft_fn


def main() -> None:  # pragma: no cover - thin live wiring
    from ed_bot.cockpit.app import CockpitApp

    cwd = str(ed_working_dir())
    course_id = resolve_course_id()
    draft_fn = build_draft_fn(cwd=cwd)

    # NOTE: post_fn / is_answered_fn / fetch_events wrap the sync ed-api client
    # via asyncio.to_thread in a follow-up; the app runs with auto-draft + chat
    # working against the agent now.
    app = CockpitApp(cwd=cwd, course_id=course_id, draft_fn=draft_fn,
                     post_fn=None, is_answered_fn=None, fetch_events=None)
    app.run()


if __name__ == "__main__":  # pragma: no cover
    main()
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_main_wiring.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/__main__.py tests/cockpit/test_main_wiring.py
git commit -m "feat(cockpit): entry point wiring the agent draft_fn"
```

---

## Task 8: Full UI suite green + manual smoke note

**Files:**
- Test: run the whole suite.

- [ ] **Step 1: Run the entire cockpit suite**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/ -q`
Expected: all green; the live SDK test stays deselected.

- [ ] **Step 2: Run the whole repo suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all green (1 deselected).

- [ ] **Step 3: Record a manual smoke instruction (no automated run)**

The real end-to-end (live agent + real forum) is validated manually, not in CI.
Append a short "Running the cockpit" section to `docs/superpowers/specs/2026-05-31-ed-cockpit-tui-design.md`:

```markdown
## Running the cockpit (manual)

From the repo root with the venv active:

    python -m ed_bot.cockpit

This launches the Textual UI. Auto-draft and chat commands run against the live
agent (from the ed working dir, so ed-api/guardrails resolve). Posting/staleness
and the real watcher poll are wired via asyncio.to_thread in a follow-up; until
then, feed events through the chat/test harness. Because the human reviews every
draft, guardrail handling stays advisory.
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-05-31-ed-cockpit-tui-design.md
git commit -m "docs(cockpit): add manual run instructions for the TUI"
```

---

## Done criteria

- `python -m ed_bot.cockpit` launches a Textual Layout-A cockpit: queue rail,
  draft viewer, status bar, chat input, alert banner.
- Forum events auto-draft and appear in the queue; selecting one shows the
  humanized draft with advisory guardrail warnings; the human approves via "post
  it" or the `a` hotkey, which posts through the loop's staleness-checked flow.
- The loop stays fully decoupled from widgets (emit → LoopEmission → routing).
- Escalations flash the alert banner.
- Whole cockpit suite green; live SDK test still `-m live`.

## Deferred (follow-up, not this plan)

- Real `fetch_events` / `post_fn` / `is_answered_fn` wrapping the sync ed-api
  client via `asyncio.to_thread`, plus the real watcher poll loop running as a
  Textual `@work` worker on an interval.
- Batch-review and canned-response modals (features 10 / 9) — scaffolded later.
- The graduation TODOs from the spike findings (typed exceptions, Protocol
  tightening) when the agent path hardens.
- Post-type vs question-type resolve handling (endorse vs accept) surfaced in
  the 2026-06-01 forum session — belongs with the posting wiring.
