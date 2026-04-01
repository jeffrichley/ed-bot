"""Guardrail loading and management."""

import pathlib
import re


class GuardrailsManager:
    """Manages per-project guardrail files."""

    def __init__(self, guardrails_dir: pathlib.Path):
        self.guardrails_dir = pathlib.Path(guardrails_dir)

    def load(self, project_slug: str) -> str | None:
        """Load guardrails for a project by slug name. Returns file content or None."""
        path = self.guardrails_dir / f"{project_slug}.md"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def list(self) -> list[str]:
        """List all available guardrail slugs."""
        if not self.guardrails_dir.exists():
            return []
        return [p.stem for p in sorted(self.guardrails_dir.glob("*.md"))]

    def detect_project(self, text: str) -> str | None:
        """Try to detect which project a question is about from the text."""
        text_lower = text.lower()
        for slug in self.list():
            # Simple heuristic: check if the slug appears in the text
            # e.g., "project1" matches "project 1" or "Project 1"
            normalized = slug.replace("-", " ").replace("_", " ")
            if normalized in text_lower or slug in text_lower:
                return slug
        return None

    @staticmethod
    def load_style_guide(path: pathlib.Path) -> str:
        """Load the global style guide. Returns content or empty string."""
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")
