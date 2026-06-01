# Cockpit Plan 3b — Chat Transcript Panel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add a two-way chat transcript to the cockpit so the human and the ed-bot agent have a visible conversation — your typed messages and ed-bot's replies — instead of a one-shot command line with only a status bar.

**Architecture:** A scrollable `ChatLog` widget sits as a band above the input (queue + draft remain the top row). Submitting in the chat input echoes a `you ▸ ...` line; the loop's text responses render as `ed-bot ▸ ...` lines. The loop gains a new emission type, `ChatMessage`, routed to the log. This plan covers the transcript + your-messages + ed-bot-replies. The agent *asking clarifying questions* (a loop change letting the agent return a question instead of a draft) is a SEPARATE follow-on plan (3c).

**Tech Stack:** Python 3.12, Textual, Pydantic v2, existing `ed_bot.cockpit` package.

**Discovered design decisions (from the 2026-06-01 manual launch):**
- The transcript turns are labelled **`you`** and **`ed-bot`** (NOT "claude").
- Placement: a band above the input; the two top panels share vertical space.
- Agent clarifying-questions appear as `ed-bot ▸` lines and the human replies by
  typing (built in plan 3c).

---

## File Structure

- `src/ed_bot/cockpit/models.py` — MODIFY: add `ChatMessage` model (role +
  text) as a new loop emission type.
- `src/ed_bot/cockpit/widgets.py` — MODIFY: add a `ChatLog` widget (scrollable,
  appends `role ▸ text` lines) and a `render_chat_line` pure helper.
- `src/ed_bot/cockpit/app.py` — MODIFY: compose the ChatLog, echo submitted
  input as a `you` line, route `ChatMessage`/freeform agent replies to it.
- `src/ed_bot/cockpit/app.tcss` — MODIFY: give the chat log a height band.
- Tests mirror under `tests/cockpit/`.

---

## Task 1: ChatMessage model

**Files:**
- Modify: `src/ed_bot/cockpit/models.py`
- Test: `tests/cockpit/test_models.py`

- [ ] **Step 1: Write the failing test** — append to `tests/cockpit/test_models.py`:

```python
def test_chat_message_roles():
    from ed_bot.cockpit.models import ChatMessage
    m = ChatMessage(role="you", text="check the forum")
    assert m.role == "you"
    assert m.text == "check the forum"
    e = ChatMessage(role="ed-bot", text="4 threads need attention")
    assert e.role == "ed-bot"


def test_chat_message_rejects_unknown_role():
    import pytest
    from pydantic import ValidationError
    from ed_bot.cockpit.models import ChatMessage
    with pytest.raises(ValidationError):
        ChatMessage(role="robot", text="x")
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_models.py -q`
Expected: FAIL — `ImportError: cannot import name 'ChatMessage'`.

- [ ] **Step 3: Implement** — add to `src/ed_bot/cockpit/models.py`, after `AlertBanner`:

```python
ChatRole = Literal["you", "ed-bot"]


class ChatMessage(BaseModel):
    """One line in the chat transcript: a human ('you') or agent ('ed-bot')
    turn. Emitted by the loop and rendered in the ChatLog."""

    role: ChatRole
    text: str
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_models.py -q`
Expected: PASS (the 12 prior + 2 new = 14 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/models.py tests/cockpit/test_models.py
git commit -m "feat(cockpit): add ChatMessage model (you/ed-bot turns)"
```

---

## Task 2: ChatLog widget

**Files:**
- Modify: `src/ed_bot/cockpit/widgets.py`
- Test: `tests/cockpit/test_widgets.py`

- [ ] **Step 1: Write the failing test** — append to `tests/cockpit/test_widgets.py`:

```python
def test_render_chat_line_formats_role_and_text():
    from ed_bot.cockpit.widgets import render_chat_line
    from ed_bot.cockpit.models import ChatMessage
    line = render_chat_line(ChatMessage(role="you", text="post it"))
    assert "you" in line
    assert "post it" in line
    bot = render_chat_line(ChatMessage(role="ed-bot", text="posted #207"))
    assert "ed-bot" in bot
    assert "posted #207" in bot
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_widgets.py -q`
Expected: FAIL — `ImportError: cannot import name 'render_chat_line'`.

- [ ] **Step 3: Implement** — add to `src/ed_bot/cockpit/widgets.py`. Add the
import `from ed_bot.cockpit.models import ChatMessage` to the existing models
import, and add this helper (near `render_draft`) plus the widget (after
`AlertBanner`):

```python
def render_chat_line(msg: ChatMessage) -> str:
    """One transcript line: 'role > text'."""
    return f"{msg.role} ▸ {msg.text}"
```

```python
class ChatLog(VerticalScroll):
    """Scrollable transcript of you/ed-bot turns."""

    def add(self, msg: ChatMessage) -> None:
        self.mount(Static(render_chat_line(msg)))
        self.scroll_end(animate=False)
```

Add the needed imports at the top of widgets.py:
`from textual.containers import VerticalScroll`.

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_widgets.py -q`
Expected: PASS (6 prior + 1 new = 7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/widgets.py tests/cockpit/test_widgets.py
git commit -m "feat(cockpit): add ChatLog widget with render_chat_line helper"
```

---

## Task 3: Wire the ChatLog into the app

**Files:**
- Modify: `src/ed_bot/cockpit/app.py`, `src/ed_bot/cockpit/app.tcss`
- Test: `tests/cockpit/test_app_chat.py`

- [ ] **Step 1: Write the failing test** — create `tests/cockpit/test_app_chat.py`:

```python
"""Tests for the chat transcript: your messages echo, ed-bot replies render."""
import pytest

from ed_bot.cockpit.app import CockpitApp
from ed_bot.cockpit.widgets import ChatLog
from ed_bot.cockpit.models import DraftPayload, ChatMessage


def _make_app():
    async def draft_fn(*, number, **kw):
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question="q", body="b", confidence="HIGH")
    return CockpitApp(cwd=".", course_id=98559, draft_fn=draft_fn,
                      post_fn=None, is_answered_fn=None, fetch_events=None)


@pytest.mark.anyio
async def test_submitting_echoes_you_line():
    app = _make_app()
    async with app.run_test() as pilot:
        chat = app.query_one("#chat")
        chat.value = "check the forum"
        await pilot.press("enter")
        await pilot.pause()
        log = app.query_one(ChatLog)
        text = "\n".join(str(s.content) for s in log.query("Static"))
        assert "you" in text and "check the forum" in text


@pytest.mark.anyio
async def test_chat_message_emission_renders_ed_bot_line():
    app = _make_app()
    async with app.run_test() as pilot:
        app._emit(ChatMessage(role="ed-bot", text="4 threads need attention"))
        await pilot.pause()
        log = app.query_one(ChatLog)
        text = "\n".join(str(s.content) for s in log.query("Static"))
        assert "ed-bot" in text and "4 threads need attention" in text
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_app_chat.py -q`
Expected: FAIL — no ChatLog mounted / no echo.

- [ ] **Step 3: Update the CSS** — in `src/ed_bot/cockpit/app.tcss`, add a
`#chatlog` block before `#status`:

```css
#chatlog {
    height: 8;
    border: solid $primary;
}
```

- [ ] **Step 4: Update the app** — in `src/ed_bot/cockpit/app.py`:

(a) Add `ChatLog` to the widgets import and `ChatMessage` to the models import.

(b) In `compose`, add the ChatLog between the StatusBar and the Input:
```python
        yield StatusBar(id="status")
        yield ChatLog(id="chatlog")
        yield Input(placeholder="type a command (e.g. 'post it')", id="chat")
```

(c) In `on_loop_emission`, add a branch:
```python
        elif isinstance(payload, ChatMessage):
            self.query_one(ChatLog).add(payload)
```

(d) In `on_input_submitted`, echo the human line before dispatching. After
`event.input.value = ""` and the empty guard, add:
```python
        self.query_one(ChatLog).add(ChatMessage(role="you", text=text))
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_app_chat.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Whole suite**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/ -q`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src/ed_bot/cockpit/app.py src/ed_bot/cockpit/app.tcss tests/cockpit/test_app_chat.py
git commit -m "feat(cockpit): chat transcript panel (you + ed-bot turns)"
```

---

## Done criteria

- A scrollable chat band sits above the input; submitting echoes `you ▸ ...`;
  a `ChatMessage` emission renders `ed-bot ▸ ...`.
- Whole cockpit suite green.

## Deferred to Plan 3c (the harder half)

- The agent *initiating* a clarifying question mid-draft (a loop change: the
  agent can return a question instead of a draft; the loop routes it to the
  chat and waits for the human's typed reply before continuing). That is what
  makes ed-bot truly interactive, and it needs new model/loop work, not just a
  widget.
