# Cockpit Plan 3d — Selectable Queue + Multi-Seed — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or executing-plans. Steps use `- [ ]`.

**Goal:** Make the queue rail a navigable, selectable list so the human can
arrow/click through multiple threads and press Enter to open one into the draft
viewer — and let `--seed` take several thread numbers so this is testable.

**Architecture:** Replace the display-only `Static` `QueueRail` with a Textual
`OptionList`. Each queue item becomes an option whose `id` is the thread number
(as a string) and whose prompt is the rendered line. An `OptionList.OptionSelected`
handler in the app opens that thread (reusing the existing open path:
`inject_command(UserCommand(intent="open", thread=N))`). A `QueueUpdate`
re-render preserves the current highlight so navigation isn't disrupted.
`--seed` parses a comma-separated list and injects one event per number.

**Tech Stack:** Python 3.12, Textual (OptionList), existing cockpit package.

**Verified Textual API (OptionList):** `add_option(Option(prompt, id=...))`,
`clear_options()`, reactive `highlighted: int | None`, message
`OptionList.OptionSelected` with `.option_id`. Arrow keys move the highlight;
Enter fires `OptionSelected`. Testable via `pilot.press("down")` /
`pilot.press("enter")`.

---

## File Structure

- `src/ed_bot/cockpit/widgets.py` — MODIFY: `QueueRail` becomes an `OptionList`
  subclass with a `show(items)` that rebuilds options and preserves highlight.
- `src/ed_bot/cockpit/app.py` — MODIFY: add `on_option_list_option_selected`
  to open the highlighted thread.
- `src/ed_bot/cockpit/app.tcss` — MODIFY: keep `#queue` sizing (OptionList
  honors the same width/height).
- `src/ed_bot/cockpit/__main__.py` — MODIFY: `--seed` accepts a comma list.
- Tests mirror under `tests/cockpit/`.

---

## Task 1: QueueRail becomes a selectable OptionList

**Files:**
- Modify: `src/ed_bot/cockpit/widgets.py`
- Test: `tests/cockpit/test_widgets.py`

- [ ] **Step 1: Write the failing test** — append to `tests/cockpit/test_widgets.py`:

```python
def test_queue_rail_is_option_list_and_renders_items():
    from textual.widgets import OptionList
    from ed_bot.cockpit.widgets import QueueRail, queue_option_text
    # QueueRail must be an OptionList subclass now.
    assert issubclass(QueueRail, OptionList)
    # The per-item text helper still includes number + title.
    text = queue_option_text(_item(number=207, title="Figure 1 graph"))
    assert "207" in text and "Figure 1 graph" in text
```

(`_item` already exists at the top of this test file.)

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_widgets.py -q`
Expected: FAIL — `ImportError: cannot import name 'queue_option_text'` / QueueRail
is not an OptionList.

- [ ] **Step 3: Implement** — in `src/ed_bot/cockpit/widgets.py`:

(a) Add imports near the top:
```python
from textual.widgets import OptionList
from textual.widgets.option_list import Option
```

(b) Rename the queue render helper and keep its formatting. Replace
`render_queue_line` usage in `QueueRail` with a module function
`queue_option_text` (same body as `render_queue_line`). Keep `render_queue_line`
as an alias for any other callers:
```python
def queue_option_text(item: QueueItem) -> str:
    """One option label for the queue rail."""
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


# Backwards-compatible alias (older tests/callers).
render_queue_line = queue_option_text
```
(If `render_queue_line` is already defined above with this body, replace its
definition with the `queue_option_text` version + alias rather than duplicating.)

(c) Replace the `QueueRail(Static)` class with an `OptionList` version:
```python
class QueueRail(OptionList):
    """Left rail: a selectable list of actionable threads.

    Each option's id is the thread number (str). Re-rendering on a QueueUpdate
    preserves the current highlight so navigation isn't disrupted."""

    def show(self, items: list[QueueItem]) -> None:
        prev = self.highlighted
        self.clear_options()
        if not items:
            self.add_option(Option("(queue empty)", id="__empty__"))
            return
        for item in items:
            self.add_option(Option(queue_option_text(item), id=str(item.number)))
        # Restore highlight position if still in range.
        if prev is not None and prev < len(items):
            self.highlighted = prev
        elif items:
            self.highlighted = 0
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_widgets.py -q`
Expected: PASS (prior widget tests + the new one).

- [ ] **Step 5: Commit**

```bash
git add src/ed_bot/cockpit/widgets.py tests/cockpit/test_widgets.py
git commit -m "feat(cockpit): queue rail becomes a selectable OptionList"
```

---

## Task 2: app opens the selected thread

**Files:**
- Modify: `src/ed_bot/cockpit/app.py`
- Test: `tests/cockpit/test_app_queue_select.py`

- [ ] **Step 1: Write the failing test** — create `tests/cockpit/test_app_queue_select.py`:

```python
"""Selecting a queue item opens its draft in the viewer."""
import pytest

from ed_bot.cockpit.app import CockpitApp
from ed_bot.cockpit.widgets import QueueRail, DraftViewer
from ed_bot.cockpit.models import WatcherEvent, DraftPayload


def _make_app():
    async def draft_fn(*, number, **kw):
        return DraftPayload(thread_id=8100000 + number, number=number,
                            question=f"q{number}", body=f"body {number}",
                            confidence="HIGH")
    return CockpitApp(cwd=".", course_id=98559, draft_fn=draft_fn,
                      post_fn=None, is_answered_fn=None, fetch_events=None)


@pytest.mark.anyio
async def test_selecting_queue_item_opens_its_draft():
    app = _make_app()
    async with app.run_test() as pilot:
        # Two events auto-draft into the queue.
        await app.inject_event(WatcherEvent(
            kind="new_thread", thread_id=8100207, number=207, title="t207",
            category="Project 1 | Martingale", url="u"))
        await app.inject_event(WatcherEvent(
            kind="new_thread", thread_id=8100225, number=225, title="t225",
            category="Project 1 | Martingale", url="u"))
        await pilot.pause()
        rail = app.query_one(QueueRail)
        rail.focus()
        # Highlight the second item and select it.
        rail.highlighted = 1
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        draft_text = str(app.query_one(DraftViewer).content)
        assert "body 225" in draft_text
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_app_queue_select.py -q`
Expected: FAIL — selecting does nothing; the draft viewer doesn't show 225.

- [ ] **Step 3: Implement** — add to `CockpitApp` in `src/ed_bot/cockpit/app.py`:

```python
    def on_option_list_option_selected(self, event) -> None:
        """A queue item was chosen: open its draft (same as 'open N')."""
        option_id = event.option_id
        if option_id is None or option_id == "__empty__":
            return
        self.inject_command(UserCommand(intent="open", thread=int(option_id)))
```

(`UserCommand` is already imported.)

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_app_queue_select.py -q`
Expected: PASS (1 passed). If the draft hasn't rendered, add one more
`await pilot.pause()` (the open path goes through an @work worker).

- [ ] **Step 5: Whole suite**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/ -q`
Expected: all green. (Note: tests that asserted `str(QueueRail.content)` for a
Static no longer apply — those were in `test_app_compose.py`; if any fail
because QueueRail is now an OptionList, update them to assert via the OptionList
option prompts, e.g. check `rail.get_option_at_index(0).prompt`.)

- [ ] **Step 6: Commit**

```bash
git add src/ed_bot/cockpit/app.py tests/cockpit/test_app_queue_select.py
git commit -m "feat(cockpit): selecting a queue item opens its draft"
```

---

## Task 3: fix any QueueRail-as-Static assertions broken by the change

**Files:**
- Modify: `tests/cockpit/test_app_compose.py` (and any other test asserting
  `QueueRail.content`/`renderable`).

- [ ] **Step 1: Find broken assertions**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/ -q`
Look for failures referencing QueueRail content. The known one is
`test_event_autodrafts_and_queue_rail_updates` in `test_app_compose.py` which
does `assert "207" in str(rail.renderable)`.

- [ ] **Step 2: Update them** to query the OptionList instead. For the
`test_app_compose.py` case, replace the assertion body with:
```python
        rail = app.query_one(QueueRail)
        labels = [rail.get_option_at_index(i).prompt
                  for i in range(rail.option_count)]
        assert any("207" in str(l) for l in labels)
```

- [ ] **Step 3: Run to verify**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/ -q`
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add tests/cockpit/test_app_compose.py
git commit -m "test(cockpit): update queue assertions for OptionList rail"
```

---

## Task 4: multi-seed (`--seed 222,225,226`)

**Files:**
- Modify: `src/ed_bot/cockpit/__main__.py`
- Test: `tests/cockpit/test_main_wiring.py`

- [ ] **Step 1: Write the failing test** — append to `tests/cockpit/test_main_wiring.py`:

```python
def test_parse_seed_numbers_handles_list():
    from ed_bot.cockpit.__main__ import parse_seed_numbers
    assert parse_seed_numbers("222") == [222]
    assert parse_seed_numbers("222,225,226") == [222, 225, 226]
    assert parse_seed_numbers("222, 225 ,226") == [222, 225, 226]
    assert parse_seed_numbers(None) == []
    assert parse_seed_numbers("") == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_main_wiring.py -q`
Expected: FAIL — `ImportError: cannot import name 'parse_seed_numbers'`.

- [ ] **Step 3: Implement** — in `src/ed_bot/cockpit/__main__.py`:

(a) Add the parser helper (near `build_seed_event`):
```python
def parse_seed_numbers(raw: str | None) -> list[int]:
    """Parse a --seed value ('222' or '222,225,226') into a list of ints."""
    if not raw:
        return []
    return [int(part.strip()) for part in raw.split(",") if part.strip()]
```

(b) Change the argparse type from `int` to `str`:
```python
    parser.add_argument("--seed", type=str, default=None,
                        help="thread number(s) to seed on startup, comma-separated")
```

(c) Replace the single-seed block in `main()`:
```python
    seed_numbers = parse_seed_numbers(args.seed)
    if seed_numbers:
        async def _seed() -> None:
            for number in seed_numbers:
                await app.inject_event(build_seed_event(number, course_id))
        app.call_after_refresh(_seed)
```
(Remove the old `if args.seed is not None:` block.)

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/test_main_wiring.py -q`
Expected: PASS.

- [ ] **Step 5: Whole suite + commit**

Run: `.venv/Scripts/python.exe -m pytest tests/cockpit/ -q` → all green.

```bash
git add src/ed_bot/cockpit/__main__.py tests/cockpit/test_main_wiring.py
git commit -m "feat(cockpit): --seed accepts multiple thread numbers"
```

---

## Done criteria

- The queue rail is a navigable `OptionList`: arrow keys move the highlight,
  Enter (or click) opens that thread's draft into the viewer.
- `QueueUpdate` re-renders preserve the highlight.
- `--seed 222,225,226` populates multiple items so multi-item selection is
  testable end to end.
- Whole cockpit suite green.

## Manual test (after build)

```
.venv/Scripts/python.exe -m ed_bot.cockpit --seed 222,225,226
```
Wait for the three items to reach `[ready]`, arrow down/up to highlight one,
press Enter — its draft fills the right panel. Repeat for another to confirm
switching works.
