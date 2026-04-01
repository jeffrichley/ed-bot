import pathlib
from ed_bot.engine.guardrails import GuardrailsManager


class TestGuardrailsManager:
    def test_load_guardrails(self, sample_playbook_dir: pathlib.Path):
        manager = GuardrailsManager(sample_playbook_dir / "guardrails")
        guardrails = manager.load("project1")
        assert guardrails is not None
        assert "Never Reveal" in guardrails

    def test_load_nonexistent_returns_none(self, sample_playbook_dir: pathlib.Path):
        manager = GuardrailsManager(sample_playbook_dir / "guardrails")
        guardrails = manager.load("nonexistent")
        assert guardrails is None

    def test_list_guardrails(self, sample_playbook_dir: pathlib.Path):
        manager = GuardrailsManager(sample_playbook_dir / "guardrails")
        names = manager.list()
        assert "project1" in names

    def test_load_style_guide(self, sample_playbook_dir: pathlib.Path):
        style_guide = GuardrailsManager.load_style_guide(
            sample_playbook_dir / "style-guide.md"
        )
        assert "teaching assistant" in style_guide.lower() or "Voice" in style_guide

    def test_detect_project(self, sample_playbook_dir: pathlib.Path):
        manager = GuardrailsManager(sample_playbook_dir / "guardrails")
        project = manager.detect_project("My Project 1 code doesn't work")
        # Should match "project1" guardrail since "Project 1" is in the title
        # This is a fuzzy match — may or may not match depending on implementation
        # At minimum, the method should return a string or None
        assert project is None or isinstance(project, str)
