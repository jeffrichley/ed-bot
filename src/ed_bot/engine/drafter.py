"""Draft generation using Claude API."""

import anthropic

from ed_bot.engine.classifier import QuestionType
from ed_bot.engine.templates import get_system_prompt


class DraftGenerator:
    """Generates draft answers using Claude API with context and guardrails."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model

    def generate(
        self,
        question: str,
        question_type: QuestionType,
        context,  # RetrievedContext
        style_guide: str,
        guardrails: str | None = None,
        existing_comments: str = "",
        hint: str | None = None,
    ) -> str:
        """Generate a draft answer.

        Returns the draft text as a string.
        """
        system_prompt = get_system_prompt(
            style_guide=style_guide,
            guardrails=guardrails,
            question_type=question_type,
        )

        context_text = context.format_for_prompt()

        user_message = f"""## Student's Question

{question}"""

        if existing_comments:
            user_message += f"""

## Existing Comments on This Thread

{existing_comments}"""

        user_message += f"""

## Retrieved Context from Knowledge Base

{context_text}"""

        if hint:
            user_message += f"""

## Instructor Guidance

{hint}"""

        user_message += """

## Your Task

Write a response to the student's question following the style guide and guardrails above.
Use the retrieved context to inform your answer. Reference specific course materials when relevant.
Do NOT make up information. If you're unsure, say so."""

        client = anthropic.Anthropic()
        response = client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        return response.content[0].text
