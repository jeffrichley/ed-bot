# Response Templates

`TEMPLATE_INSTRUCTIONS` in `ed_bot.engine.templates` maps each `QuestionType` to a compact instruction string that is appended to the system prompt under a `## Response Style for This Question` heading.

## Template definitions

```python
TEMPLATE_INSTRUCTIONS: dict[QuestionType, str] = {
    QuestionType.LOGISTICS: (
        "Respond in a direct, factual tone. Include specific dates, links, "
        "or steps. No Socratic method — just answer the question clearly."
    ),
    QuestionType.SETUP: (
        "Provide step-by-step instructions. Be specific about commands, "
        "paths, and environment details. Include common pitfalls."
    ),
    QuestionType.CONCEPTUAL: (
        "Use a Socratic approach: ask guiding questions before giving the full answer. "
        "Point to relevant lectures or readings. Build understanding, don't just state facts."
    ),
    QuestionType.PROJECT_HELP: (
        "Never provide solution code or reveal implementation details. "
        "Ask what they've tried. Point to relevant concepts and documentation. "
        "If their approach is fundamentally wrong, redirect gently. "
        "Reference similar past threads when applicable."
    ),
    QuestionType.TEACHING_MOMENT: (
        "Be thorough — this is an opportunity to educate. Use examples, analogies, "
        "and step-by-step reasoning. Reference lecture content when possible."
    ),
    QuestionType.INTEGRITY_RISK: (
        "This appears to be a potential academic integrity issue. "
        "Do NOT answer the question. Suggest the thread be marked private. "
        "Note what makes this a concern."
    ),
}
```

## Template-to-question-type mapping

| QuestionType | Template behavior |
|-------------|-------------------|
| `logistics` | Direct, no Socratic probing. Give dates, links, steps immediately. |
| `setup` | Step-by-step instructions with specific commands. Mention common pitfalls. |
| `conceptual` | Socratic: guiding questions first, references to lectures and readings. |
| `project_help` | No solution code. Ask what was tried. Redirect if approach is wrong. |
| `teaching_moment` | Thorough educational response with examples and analogies. |
| `integrity_risk` | Refuse to answer. Flag for private review. State concern clearly. |

## Using templates programmatically

```python
from ed_bot.engine.classifier import QuestionType
from ed_bot.engine.templates import get_template_instructions, get_system_prompt

# Fetch a single template's instructions
instructions = get_template_instructions(QuestionType.CONCEPTUAL)

# Build a complete system prompt
prompt = get_system_prompt(
    style_guide=style_guide_text,
    guardrails=project_guardrail_text,
    question_type=QuestionType.PROJECT_HELP,
)
```

`get_template_instructions()` falls back to `PROJECT_HELP` if the question type is not found in the dictionary.

## Customizing template behavior

The current design intentionally keeps templates short — they complement the style guide rather than duplicate it. If you want to change how a question type is handled:

1. Edit the style guide section for that question type to change the human-readable description.
2. Edit `TEMPLATE_INSTRUCTIONS` in `ed_bot/engine/templates.py` to change the Claude-facing instruction.

Keep the two in sync so reviewers understand why Claude behaves as it does.

## Integrity risk handling

When a thread is classified as `INTEGRITY_RISK`, the template instructs Claude to:

- Explicitly refuse to answer the substantive question
- Explain what signals triggered the concern (e.g., "asks for the exact return formula")
- Recommend marking the thread private for staff review

The draft will still be created and placed in the queue so a staff member can review the flagged thread and decide whether to act.
