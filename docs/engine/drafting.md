# Draft Generation

`DraftGenerator` builds a complete system prompt from the style guide, question-type instructions, and project guardrails, then calls the Claude API with retrieved context to produce a draft answer.

## How it works

The generation pipeline runs inside `ed answer`:

```
thread
  │
  ├─▶ ThreadClassifier.classify_status()   ──▶  ThreadStatus
  │
  ├─▶ GuardrailsManager.detect_project()   ──▶  project_slug
  │
  ├─▶ GuardrailsManager.load()             ──▶  guardrails text
  │
  ├─▶ GuardrailsManager.load_style_guide() ──▶  style guide text
  │
  ├─▶ ContextRetriever.retrieve()          ──▶  RetrievedContext
  │                                              ├─ past Q&A chunks
  │                                              ├─ project material chunks
  │                                              └─ lecture content chunks
  │
  └─▶ DraftGenerator.generate()            ──▶  draft text
```

## DraftGenerator

```python
class DraftGenerator:
    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model

    def generate(
        self,
        question: str,
        question_type: QuestionType,
        context: RetrievedContext,
        style_guide: str,
        guardrails: str | None = None,
        existing_comments: str = "",
        hint: str | None = None,
    ) -> str: ...
```

The `hint` parameter lets reviewers or Claude Code skills pass instructor guidance into the prompt (via `ed answer <id> --hint "..."`) without modifying the style guide.

## System prompt construction

`get_system_prompt()` in `ed_bot.engine.templates` assembles three parts in order:

1. **Style guide** — the global TA persona and formatting rules
2. **Question-type instructions** — from `TEMPLATE_INSTRUCTIONS[question_type]`
3. **Project guardrails** — injected only when a guardrail file was found

```python
def get_system_prompt(
    style_guide: str,
    guardrails: str | None = None,
    question_type: QuestionType | None = None,
) -> str:
    parts = [style_guide]
    if question_type:
        parts.append(f"\n## Response Style for This Question\n\n"
                     f"{get_template_instructions(question_type)}")
    if guardrails:
        parts.append(f"\n## Project Guardrails\n\n{guardrails}")
    return "\n\n".join(parts)
```

## User message structure

The user turn contains four sections, assembled in order:

```
## Student's Question

<thread body in markdown>

## Existing Comments on This Thread       ← omitted if empty

<comment history>

## Retrieved Context from Knowledge Base

### Relevant Past Q&A
---
Source: threads/fall2025/0287-sharpe-nan.md
...

### Relevant Project Materials
---
Source: projects/project2-requirements.md
...

## Instructor Guidance                    ← omitted if no hint

<hint text>

## Your Task

Write a response to the student's question following the style guide and
guardrails above. Use the retrieved context to inform your answer.
Reference specific course materials when relevant. Do NOT make up
information. If you're unsure, say so.
```

## Model configuration

The default model is `claude-sonnet-4-20250514` with `max_tokens=2048`. To use a different model, pass it to the constructor:

```python
generator = DraftGenerator(model="claude-opus-4-5")
```

The Anthropic client is instantiated per-call and reads `ANTHROPIC_API_KEY` from the environment.

## Context retrieval

`ContextRetriever.retrieve()` searches all indexed pyqmd collections (threads, projects, lectures) for the top-10 most relevant chunks. Results are partitioned by source type so the prompt clearly delineates past Q&A from project materials from lecture content.

```python
context = retriever.retrieve(query, project=project_slug, top_k=10)
context.thread_chunks    # from threads/
context.project_chunks   # from projects/
context.lecture_chunks   # from lectures/
context.format_for_prompt()  # formatted string for the LLM
```
