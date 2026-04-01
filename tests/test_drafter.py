from unittest.mock import MagicMock, patch
from ed_bot.engine.drafter import DraftGenerator
from ed_bot.engine.classifier import QuestionType


class TestDraftGenerator:
    def test_generate_returns_content(self):
        mock_context = MagicMock()
        mock_context.format_for_prompt.return_value = "Past answer about NaN"

        with patch("ed_bot.engine.drafter.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="The NaN values are expected because...")]
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            generator = DraftGenerator()
            result = generator.generate(
                question="My data has NaN values",
                question_type=QuestionType.PROJECT_HELP,
                context=mock_context,
                style_guide="Be helpful",
                guardrails="Never reveal solutions",
            )

            assert "NaN" in result
            mock_client.messages.create.assert_called_once()

    def test_generate_includes_guardrails_in_prompt(self):
        mock_context = MagicMock()
        mock_context.format_for_prompt.return_value = ""

        with patch("ed_bot.engine.drafter.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Response")]
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            generator = DraftGenerator()
            generator.generate(
                question="help me",
                question_type=QuestionType.PROJECT_HELP,
                context=mock_context,
                style_guide="Be nice",
                guardrails="## Never Reveal\n- Solution code",
            )

            call_args = mock_client.messages.create.call_args
            system = call_args[1].get("system") or (call_args[0][0] if call_args[0] else "")
            # The system prompt should contain guardrails
            messages = call_args[1].get("messages", [])
            all_text = str(system) + str(messages)
            assert "Never Reveal" in all_text or "Solution code" in all_text

    def test_generate_uses_correct_model(self):
        mock_context = MagicMock()
        mock_context.format_for_prompt.return_value = ""

        with patch("ed_bot.engine.drafter.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Response")]
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            generator = DraftGenerator(model="claude-opus-4-5")
            generator.generate(
                question="Question",
                question_type=QuestionType.CONCEPTUAL,
                context=mock_context,
                style_guide="Guide",
            )

            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["model"] == "claude-opus-4-5"

    def test_generate_includes_hint_when_provided(self):
        mock_context = MagicMock()
        mock_context.format_for_prompt.return_value = ""

        with patch("ed_bot.engine.drafter.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Response")]
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            generator = DraftGenerator()
            generator.generate(
                question="Question",
                question_type=QuestionType.CONCEPTUAL,
                context=mock_context,
                style_guide="Guide",
                hint="Point to lecture 5",
            )

            call_kwargs = mock_client.messages.create.call_args[1]
            messages = call_kwargs["messages"]
            user_content = messages[0]["content"]
            assert "Point to lecture 5" in user_content
            assert "Instructor Guidance" in user_content

    def test_generate_no_guardrails(self):
        mock_context = MagicMock()
        mock_context.format_for_prompt.return_value = "Some context"

        with patch("ed_bot.engine.drafter.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Answer without guardrails")]
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            generator = DraftGenerator()
            result = generator.generate(
                question="What is a martingale?",
                question_type=QuestionType.CONCEPTUAL,
                context=mock_context,
                style_guide="Be educational",
                guardrails=None,
            )

            assert result == "Answer without guardrails"
            mock_client.messages.create.assert_called_once()
