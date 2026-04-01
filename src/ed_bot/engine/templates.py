"""Response templates by question type."""

from ed_bot.engine.classifier import QuestionType


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


def get_template_instructions(question_type: QuestionType) -> str:
    """Get response instructions for a question type."""
    return TEMPLATE_INSTRUCTIONS.get(question_type, TEMPLATE_INSTRUCTIONS[QuestionType.PROJECT_HELP])


def get_system_prompt(
    style_guide: str,
    guardrails: str | None = None,
    question_type: QuestionType | None = None,
) -> str:
    """Build the system prompt for draft generation."""
    parts = [style_guide]

    if question_type:
        parts.append(f"\n## Response Style for This Question\n\n{get_template_instructions(question_type)}")

    if guardrails:
        parts.append(f"\n## Project Guardrails\n\n{guardrails}")

    return "\n\n".join(parts)
