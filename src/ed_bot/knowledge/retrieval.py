"""Context retrieval for answer generation."""

from dataclasses import dataclass, field


@dataclass
class RetrievedContext:
    """Context retrieved from the knowledge base for answer generation."""

    chunks: list = field(default_factory=list)  # all retrieved chunks
    scores: list[float] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)

    @property
    def thread_chunks(self) -> list:
        return [c for c in self.chunks if "threads/" in c.source_file]

    @property
    def project_chunks(self) -> list:
        return [c for c in self.chunks if "projects/" in c.source_file]

    @property
    def lecture_chunks(self) -> list:
        return [c for c in self.chunks if "lectures/" in c.source_file]

    def format_for_prompt(self) -> str:
        """Format retrieved context for inclusion in an LLM prompt."""
        sections = []

        if self.thread_chunks:
            sections.append("## Relevant Past Q&A\n")
            for chunk in self.thread_chunks:
                sections.append(f"---\nSource: {chunk.source_file}\n{chunk.content}\n")

        if self.project_chunks:
            sections.append("## Relevant Project Materials\n")
            for chunk in self.project_chunks:
                sections.append(f"---\nSource: {chunk.source_file}\n{chunk.content}\n")

        if self.lecture_chunks:
            sections.append("## Relevant Lecture Content\n")
            for chunk in self.lecture_chunks:
                sections.append(f"---\nSource: {chunk.source_file}\n{chunk.content}\n")

        return "\n".join(sections) if sections else "No relevant context found."


class ContextRetriever:
    """Retrieves relevant context from the knowledge base."""

    def __init__(self, knowledge_base):
        self.kb = knowledge_base

    def retrieve(
        self,
        query: str,
        project: str | None = None,
        top_k: int = 10,
    ) -> RetrievedContext:
        """Retrieve relevant context for a question."""
        results = self.kb.search(query, top_k=top_k)

        context = RetrievedContext()
        for result in results:
            context.chunks.append(result.chunk)
            context.scores.append(result.score)
            context.source_files.append(result.chunk.source_file)

        return context
