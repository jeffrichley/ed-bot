# Cockpit Plan 3c (part 1) — ed-bot Replies in Chat — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or executing-plans. Steps use `- [ ]`.

**Goal:** Make ed-bot actually talk back in the chat transcript: a `freeform`
message routes to the live agent and its answer renders as an `ed-bot ▸` line; a
`check_forum` command replies with a summary of the current queue. This is the
first thing that lets a human converse with the headless brain and verify it
works live.

**Architecture:** The `CockpitLoop` gains an injected `chat_fn` (text → agent
reply string). `_on_command` handles two more intents: `freeform` (call
`chat_fn`, emit `ChatMessage(role="ed-bot", text=reply)`) and `check_forum`
(emit a `ChatMessage` summarizing the in-memory queue). The agent module gains
`chat_reply`, a plain (non-structured) SDK call using the existing cockpit
config. The app already routes `ChatMessage` emissions to the `ChatLog` (built in
3b), so no UI routing change is needed — only passing `chat_fn` through.

**Tech Stack:** Python 3.12, claude-agent-sdk 0.2.87, Textual, Pydantic v2.

**Out of scope (deferred, noted honestly):**
- **Parallel drafting.** The loop stays a single sequential consumer; multiple
  events draft one at a time. Fan-out of concurrent SDK instances is a future
  plan, NOT this one.
- **ed-bot asking clarifying questions mid-draft** (3c part 2).
- **Live forum scan in `check_forum`** — this plan summarizes the in-memory
  queue, not a fresh ed-api scan (that needs the deferred fetch wiring).

---

## File Structure

- `src/ed_bot/cockpit/agent.py` — MODIFY: add `chat_reply` (plain SDK text call,
  injected for tests).
- `src/ed_bot/cockpit/loop.py` — MODIFY: add `chat_fn` param; handle `freeform`
  and `check_forum` in `_on_command`; emit `ChatMessage`.
- `src/ed_bot/cockpit/app.py` — MODIFY: accept `chat_fn`, pass to the loop.
- `src/ed_bot/cockpit/__main__.py` — MODIFY: build the real `chat_fn` and wire
  it.
- Tests mirror under `tests/cockpit/`.

---

## Task 1: agent.chat_reply

**Files:** Modify `src/ed_bot/cockpit/agent.py`. Create `tests/cockpit/test_agent_chat.py`.

`chat_reply` runs a plain (no `output_format`) SDK query with the cockpit config
and returns the final text. The SDK call is injected for tests.

- [ ] **Step 1: Write the failing test** — create `tests/cockpit/test_agent_chat.py`:

```python
"""Tests for the freeform chat_reply agent task (injected SDK, no network)."""
import pytest

from ed_bot.cockpit import agent


@pytest.mark.anyio
async def test_chat_reply_returns_agent_text():
    async def fake_sdk_text(*, prompt, cwd):
        assert "how many threads" in prompt.lower()
        return "There are 3 open threads."

    reply = await agent.chat_reply(
        text="how many threads are open?", cwd=".", course_id=98559,
        sdk_text=fake_sdk_text,
    )
    assert reply == "There are 3 open threads."


@pytest.mark.anyio
async def test_chat_reply_passes_course_context():
    seen = {}

    async def fake_sdk_text(*, prompt, cwd):
        seen["prompt"] = prompt
        return "ok"

    await agent.chat_reply(text="hi", cwd="/ed", course_id=98559,
                           sdk_text=fake_sdk_text)
    assert "98559" in seen["prompt"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_agent_chat.py -q`
Expected: FAIL — `AttributeError: module 'ed_bot.cockpit.agent' has no attribute 'chat_reply'`.

- [ ] **Step 3: Implement** — append to `src/ed_bot/cockpit/agent.py`:

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_agent_chat.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/agent.py tests/cockpit/test_agent_chat.py
git commit -m "feat(cockpit): add chat_reply agent task for freeform chat"
```

---

## Task 2: loop handles freeform + check_forum, emits ChatMessage

**Files:** Modify `src/ed_bot/cockpit/loop.py`. Create `tests/cockpit/test_loop_chat.py`.

- [ ] **Step 1: Write the failing test** — create `tests/cockpit/test_loop_chat.py`:

```python
"""Tests for the loop's chat handling: freeform -> ed-bot reply, check_forum -> summary."""
import pytest

from ed_bot.cockpit.models import WatcherEvent, UserCommand, DraftPayload, ChatMessage
from ed_bot.cockpit.loop import CockpitLoop


async def _draft(*, number, **kw):
    return DraftPayload(thread_id=8100000 + number, number=number,
                        question="q", body="b", confidence="HIGH")


def _event(number=207):
    return WatcherEvent(kind="new_thread", thread_id=8100000 + number,
                        number=number, title=f"t{number}",
                        category="Project 1 | Martingale", url="u")


@pytest.mark.anyio
async def test_freeform_emits_ed_bot_chat_message():
    emitted = []

    async def chat_fn(*, text, cwd, course_id):
        return f"echo: {text}"

    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=_draft,
                       emit=lambda m: emitted.append(m), chat_fn=chat_fn)
    await loop.handle(UserCommand(intent="freeform", text="hello there"))

    chats = [m for m in emitted if isinstance(m, ChatMessage)]
    assert any(c.role == "ed-bot" and "echo: hello there" in c.text for c in chats)


@pytest.mark.anyio
async def test_check_forum_summarizes_queue():
    emitted = []
    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=_draft,
                       emit=lambda m: emitted.append(m))
    # Seed the queue with one auto-drafted item.
    await loop.handle(_event(207))
    emitted.clear()
    await loop.handle(UserCommand(intent="check_forum"))

    chats = [m for m in emitted if isinstance(m, ChatMessage)]
    assert chats and chats[-1].role == "ed-bot"
    assert "207" in chats[-1].text


@pytest.mark.anyio
async def test_check_forum_empty_queue_says_empty():
    emitted = []
    loop = CockpitLoop(cwd=".", course_id=98559, draft_fn=_draft,
                       emit=lambda m: emitted.append(m))
    await loop.handle(UserCommand(intent="check_forum"))
    chats = [m for m in emitted if isinstance(m, ChatMessage)]
    assert chats and "empty" in chats[-1].text.lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_loop_chat.py -q`
Expected: FAIL — `CockpitLoop.__init__` has no `chat_fn`; freeform/check_forum emit nothing.

- [ ] **Step 3: Implement** — in `src/ed_bot/cockpit/loop.py`:

(a) Add `ChatMessage` to the models import:
```python
from ed_bot.cockpit.models import (
    WatcherEvent, UserCommand, QueueItem, QueueUpdate, DraftPayload, StatusUpdate,
    ActionResult, ChatMessage,
)
```

(b) Add a type alias near the others:
```python
ChatFn = Callable[..., Awaitable[str]]
```

(c) Extend `__init__` to accept and store `chat_fn` (add the param at the end,
default None):
```python
    def __init__(self, *, cwd: str, course_id: int, draft_fn: DraftFn,
                 emit: Emit, post_fn: "PostFn | None" = None,
                 is_answered_fn: "IsAnsweredFn | None" = None,
                 chat_fn: "ChatFn | None" = None) -> None:
        self._cwd = cwd
        self._course_id = course_id
        self._draft_fn = draft_fn
        self._emit = emit
        self._post_fn = post_fn
        self._is_answered_fn = is_answered_fn
        self._chat_fn = chat_fn
        self._items: dict[int, QueueItem] = {}
        self._drafts: dict[int, DraftPayload] = {}
```

(d) Replace `_on_command` to handle the two new intents (keep open + approve):
```python
    async def _on_command(self, cmd: UserCommand):
        if cmd.intent == "open" and cmd.thread is not None:
            return self._drafts.get(cmd.thread)
        if cmd.intent == "approve" and cmd.thread is not None:
            return await self._approve(cmd.thread)
        if cmd.intent == "check_forum":
            self._emit_queue_summary()
            return None
        if cmd.intent == "freeform" and self._chat_fn is not None:
            reply = await self._chat_fn(
                text=cmd.text or "", cwd=self._cwd, course_id=self._course_id,
            )
            self._emit(ChatMessage(role="ed-bot", text=reply))
            return None
        return None

    def _emit_queue_summary(self) -> None:
        items = list(self._items.values())
        if not items:
            self._emit(ChatMessage(role="ed-bot", text="The queue is empty."))
            return
        parts = [f"#{i.number} ({i.draft_state})" for i in items]
        self._emit(ChatMessage(
            role="ed-bot",
            text=f"{len(items)} in queue: " + ", ".join(parts)))
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_loop_chat.py -q`
Expected: PASS (3 passed). Also run `.venv/Scripts/python.exe -m pytest tests/cockpit/test_loop.py tests/cockpit/test_loop_post.py -q` → still green (existing loop tests unaffected).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/loop.py tests/cockpit/test_loop_chat.py
git commit -m "feat(cockpit): loop emits ed-bot chat replies for freeform and check_forum"
```

---

## Task 3: pass chat_fn through the app + entry point

**Files:** Modify `src/ed_bot/cockpit/app.py`, `src/ed_bot/cockpit/__main__.py`. Create `tests/cockpit/test_app_chat_reply.py`.

- [ ] **Step 1: Write the failing test** — create `tests/cockpit/test_app_chat_reply.py`:

```python
"""Test that a freeform chat message produces an ed-bot reply line in the app."""
import pytest

from ed_bot.cockpit.app import CockpitApp
from ed_bot.cockpit.widgets import ChatLog
from ed_bot.cockpit.models import DraftPayload
from textual.widgets import Static


def _make_app():
    async def draft_fn(*, number, **kw):
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question="q", body="b", confidence="HIGH")

    async def chat_fn(*, text, cwd, course_id):
        return f"you said: {text}"

    return CockpitApp(cwd=".", course_id=98559, draft_fn=draft_fn,
                      post_fn=None, is_answered_fn=None, fetch_events=None,
                      chat_fn=chat_fn)


@pytest.mark.anyio
async def test_freeform_chat_shows_ed_bot_reply():
    app = _make_app()
    async with app.run_test() as pilot:
        chat = app.query_one("#chat")
        chat.value = "what's the deadline?"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        log = app.query_one(ChatLog)
        text = "\n".join(str(s.content) for s in log.query(Static))
        assert "you" in text and "what's the deadline?" in text
        assert "ed-bot" in text and "you said: what's the deadline?" in text
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_app_chat_reply.py -q`
Expected: FAIL — `CockpitApp.__init__` has no `chat_fn`, so no ed-bot line.

- [ ] **Step 3: Implement — `src/ed_bot/cockpit/app.py`.** Extend `__init__` to
accept `chat_fn` and pass it to the loop. Replace the `__init__` signature and
the loop construction:

```python
    def __init__(self, *, cwd: str, course_id: int, draft_fn,
                 post_fn=None, is_answered_fn=None, fetch_events=None,
                 chat_fn=None) -> None:
        super().__init__()
        self._fetch_events = fetch_events
        self._active_thread: Optional[int] = None
        self.loop = CockpitLoop(
            cwd=cwd, course_id=course_id, draft_fn=draft_fn,
            emit=self._emit, post_fn=post_fn, is_answered_fn=is_answered_fn,
            chat_fn=chat_fn,
        )
```

- [ ] **Step 4: Implement — `src/ed_bot/cockpit/__main__.py`.** Wire the real
chat_fn. Add this helper after `build_draft_fn`:

```python
from ed_bot.cockpit.agent import chat_reply as _agent_chat_reply


def build_chat_fn(*, cwd: str, chat_reply=_agent_chat_reply):
    """The loop's chat_fn: route freeform text to the agent from the ed dir."""
    async def chat_fn(*, text: str, cwd: str = cwd, course_id: int) -> str:
        return await chat_reply(text=text, cwd=cwd, course_id=course_id)
    return chat_fn
```

Then in `main()`, build it and pass it to the app. Change the `app = CockpitApp(...)`
construction to include `chat_fn`:

```python
    draft_fn = build_draft_fn(cwd=cwd)
    chat_fn = build_chat_fn(cwd=cwd)

    app = CockpitApp(cwd=cwd, course_id=course_id, draft_fn=draft_fn,
                     post_fn=None, is_answered_fn=None, fetch_events=None,
                     chat_fn=chat_fn)
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_app_chat_reply.py -q`
Expected: PASS (1 passed).

- [ ] **Step 6: Whole suite**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/ -q`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src/ed_bot/cockpit/app.py src/ed_bot/cockpit/__main__.py tests/cockpit/test_app_chat_reply.py
git commit -m "feat(cockpit): wire chat_fn so freeform chat gets a live ed-bot reply"
```

---

## Done criteria

- Typing a non-command message in the cockpit chat produces a `you ▸ ...` line
  AND an `ed-bot ▸ ...` reply from the live agent.
- "check the forum" replies with an `ed-bot ▸` queue summary.
- Whole cockpit suite green; live SDK test still `-m live`.
- This is the first path that lets a human converse with the brain and confirm
  it works live.

## Deferred (honest)

- Parallel drafting of multiple events (single sequential consumer today).
- ed-bot asking clarifying questions mid-draft (3c part 2).
- Live ed-api forum scan in `check_forum` (summarizes in-memory queue for now).
