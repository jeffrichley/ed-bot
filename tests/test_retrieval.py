from unittest.mock import MagicMock
from ed_bot.knowledge.retrieval import ContextRetriever


class TestContextRetriever:
    def test_retrieve_returns_context(self):
        mock_kb = MagicMock()
        mock_result = MagicMock()
        mock_result.chunk.content = "Past answer about NaN values"
        mock_result.chunk.source_file = "threads/spring-2025/0142.md"
        mock_result.chunk.metadata = {"category": "Project 1"}
        mock_result.score = 0.85
        mock_kb.search.return_value = [mock_result]

        retriever = ContextRetriever(mock_kb)
        context = retriever.retrieve("get_data returns NaN", project="Project 1")

        assert len(context.chunks) == 1
        assert "NaN" in context.chunks[0].content

    def test_retrieve_separates_by_source(self):
        mock_kb = MagicMock()
        thread_result = MagicMock()
        thread_result.chunk.source_file = "threads/s1/0001.md"
        thread_result.chunk.content = "Past thread"
        thread_result.chunk.metadata = {}
        thread_result.score = 0.9

        project_result = MagicMock()
        project_result.chunk.source_file = "projects/p1.md"
        project_result.chunk.content = "Project requirement"
        project_result.chunk.metadata = {}
        project_result.score = 0.8

        mock_kb.search.return_value = [thread_result, project_result]

        retriever = ContextRetriever(mock_kb)
        context = retriever.retrieve("question about project")

        assert len(context.thread_chunks) >= 1
        assert len(context.project_chunks) >= 1

    def test_format_for_prompt(self):
        mock_kb = MagicMock()
        mock_result = MagicMock()
        mock_result.chunk.content = "Relevant answer"
        mock_result.chunk.source_file = "threads/s1/0001.md"
        mock_result.chunk.metadata = {}
        mock_result.score = 0.9
        mock_kb.search.return_value = [mock_result]

        retriever = ContextRetriever(mock_kb)
        context = retriever.retrieve("question")
        prompt_text = context.format_for_prompt()

        assert isinstance(prompt_text, str)
        assert "Relevant answer" in prompt_text
