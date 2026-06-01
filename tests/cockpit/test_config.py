"""Tests for cockpit runtime config resolution."""
import textwrap

from ed_bot.cockpit.config import resolve_course_id, ed_working_dir


def test_resolve_course_id_reads_top_level_key(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(textwrap.dedent("""
        course_id: 98559
        region: us
        semesters:
          - name: summer-2026
            course_id: 98559
    """).strip(), encoding="utf-8")
    assert resolve_course_id(cfg) == 98559


def test_resolve_course_id_missing_raises(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("region: us\n", encoding="utf-8")
    try:
        resolve_course_id(cfg)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_ed_working_dir_is_absolute_and_named_ed():
    p = ed_working_dir()
    assert p.name == "ed"
    assert p.is_absolute()
