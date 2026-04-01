import pathlib
from unittest.mock import patch, MagicMock
from ed_bot.ingestion.lectures import LectureIngester, _slugify, _format_timestamp, _merge_segments


class TestHelpers:
    def test_slugify(self):
        assert _slugify("Lesson 01: Reading Data") == "lesson-01-reading-data"
        assert _slugify("  Hello World!  ") == "hello-world"

    def test_format_timestamp(self):
        assert _format_timestamp(0) == "00:00:00"
        assert _format_timestamp(65) == "00:01:05"
        assert _format_timestamp(3661) == "01:01:01"

    def test_merge_segments(self):
        segments = [
            ("00:00:00", "Hello"),
            ("00:00:05", "world"),
            ("00:00:10", "this is"),
            ("00:01:00", "a new chunk"),
        ]
        merged = _merge_segments(segments, chunk_seconds=30)
        assert len(merged) == 2
        assert "Hello" in merged[0][1]
        assert "new chunk" in merged[1][1]

    def test_merge_empty(self):
        assert _merge_segments([]) == []


class TestParsesSrt:
    def test_parse_srt(self, tmp_path: pathlib.Path):
        srt_content = """1
00:00:01,000 --> 00:00:03,000
Hello world

2
00:00:04,000 --> 00:00:06,000
This is a test

3
00:01:00,000 --> 00:01:05,000
New section here
"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(srt_content)

        config = MagicMock()
        config.lectures_dir = tmp_path / "lectures"
        ingester = LectureIngester(config)

        segments = ingester._parse_srt(srt_file)
        assert len(segments) > 0
        assert any("Hello" in s[1] for s in segments)


class TestLectureIngester:
    def test_generate_markdown(self, tmp_path: pathlib.Path):
        config = MagicMock()
        config.lectures_dir = tmp_path / "lectures"

        ingester = LectureIngester(config)
        md = ingester._generate_markdown(
            title="Lesson 01: Reading Data",
            course_id=54321,
            video_url="https://example.com/video",
            duration="0:45:22",
            segments=[
                ("00:00:00", "Welcome to the first lesson."),
                ("00:03:42", "Now let's talk about pandas."),
            ],
            slug="lesson-01-reading-data",
            lesson_id=5001,
            slide_id=9002,
            slide_title="Reading Stock Data",
        )
        assert "lecture:" in md
        assert "# Lesson 01: Reading Data" in md
        assert "[00:00:00]" in md
        assert "Welcome to the first lesson" in md
        assert "lesson_id: 5001" in md
        assert "slide_id: 9002" in md
        assert "edstem_url:" in md
        assert "video_file:" in md
