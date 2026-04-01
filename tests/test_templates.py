from ed_bot.engine.templates import get_system_prompt, get_template_instructions
from ed_bot.engine.classifier import QuestionType


class TestTemplates:
    def test_logistics_template(self):
        instructions = get_template_instructions(QuestionType.LOGISTICS)
        assert "direct" in instructions.lower() or "factual" in instructions.lower()

    def test_conceptual_template(self):
        instructions = get_template_instructions(QuestionType.CONCEPTUAL)
        assert "socratic" in instructions.lower() or "guiding" in instructions.lower()

    def test_project_help_template(self):
        instructions = get_template_instructions(QuestionType.PROJECT_HELP)
        assert "never" in instructions.lower() and "solution" in instructions.lower()

    def test_teaching_moment_template(self):
        instructions = get_template_instructions(QuestionType.TEACHING_MOMENT)
        assert "thorough" in instructions.lower()

    def test_system_prompt_includes_style(self):
        prompt = get_system_prompt(style_guide="Be helpful.", guardrails=None)
        assert "Be helpful" in prompt

    def test_system_prompt_includes_guardrails(self):
        prompt = get_system_prompt(
            style_guide="Be helpful.",
            guardrails="## Never Reveal\n- Solution code"
        )
        assert "Never Reveal" in prompt
