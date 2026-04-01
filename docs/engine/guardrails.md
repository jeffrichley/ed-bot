# Guardrails

`GuardrailsManager` loads per-project markdown files that constrain what Claude can reveal in draft answers. Guardrails are the primary mechanism for preventing academic integrity violations.

## How guardrails work

When `ed answer` runs for a thread, `GuardrailsManager.detect_project()` inspects the thread title and category to find a matching project slug. If found, the corresponding guardrail file is loaded and injected into the Claude system prompt under a `## Project Guardrails` heading.

```python
from ed_bot.engine.guardrails import GuardrailsManager

mgr = GuardrailsManager(config.guardrails_dir)

# Auto-detect from thread text
slug = mgr.detect_project("My optimize_portfolio is returning NaN - Project 2")
# "project2"

# Load the guardrail file
guardrails = mgr.load(slug)
```

## Guardrail file format

Guardrail files live in `{playbook_dir}/guardrails/{slug}.md`. The recommended structure uses three sections:

```markdown
# Project 2 Guardrails

## Never Reveal

- The formula for the optimizer's objective function
- Which scipy optimizer to use or its exact arguments
- The specific return calculation in `assess_portfolio()`
- Complete implementations of any required function

## OK to Discuss

- The concept of the Sharpe ratio and why we maximize it
- General scipy.optimize documentation and usage patterns
- How to interpret NaN or infinite values in optimization output
- Debugging strategies: print statements, smaller datasets, unit tests
- The structure of the DataFrame that `get_data()` returns

## Common Questions

### "My Sharpe ratio is NaN"
Check for division by zero in volatility calculation. Ask the student
what value `port_std` has and whether any returns are identical.

### "optimize_portfolio returns the wrong answer"
Ask what objective function they're using and whether they've verified
it manually on a small example.
```

## CLI management

### List guardrail files

```bash
ed guardrails list
```

```
  project1
  project2
  project3
  final-project
```

JSON output:

```bash
ed guardrails list --json
# ["project1", "project2", "project3", "final-project"]
```

### Edit a guardrail

Opens the file in `$EDITOR` (falls back to `notepad` on Windows or `vi` on Unix):

```bash
ed guardrails edit project2
```

If the file does not exist it will be created (as an empty file). Add your guardrail content and save.

## Project detection heuristic

`detect_project()` iterates over all available slugs and checks whether the slug (or its humanized form with spaces) appears in the question text:

```python
def detect_project(self, text: str) -> str | None:
    text_lower = text.lower()
    for slug in self.list():
        normalized = slug.replace("-", " ").replace("_", " ")
        if normalized in text_lower or slug in text_lower:
            return slug
    return None
```

This means "project 2", "project2", and "project-2" all match a slug of `project2` or `project-2`.

!!! tip "Naming convention"
    Use simple slugs that match how students refer to projects in forum posts: `project1`, `project2`, `project3`, `final`. Avoid spaces or uppercase in slug filenames.

## Style guide vs. guardrails

The **style guide** (`~/.ed-bot/playbook/style-guide.md`) applies globally to every response and defines tone, format, and general TA persona. **Guardrails** are per-project and define the specific facts, formulas, or implementation details that must not be revealed for a particular assignment.

Both are loaded and injected into the system prompt by `get_system_prompt()` in `ed_bot.engine.templates`.
