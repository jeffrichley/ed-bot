"""Lecture ingestion: video → transcript → screenshots → markdown."""

import pathlib
import re
import subprocess
import shutil
from datetime import timedelta

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from ed_bot.config import BotConfig

console = Console()


class LectureIngester:
    """Downloads lecture videos, transcribes, extracts screenshots, generates markdown."""

    def __init__(self, config: BotConfig):
        self.config = config

    def ingest_video(
        self,
        video_url: str,
        lesson_title: str,
        course_id: int,
        output_name: str | None = None,
    ) -> int:
        """Ingest a single video. Returns 1 on success, 0 on failure."""
        slug = output_name or _slugify(lesson_title)
        output_dir = self.config.lectures_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        screenshot_dir = output_dir / slug
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        video_path = screenshot_dir / "video.mp4"
        audio_path = screenshot_dir / "audio.wav"

        # Step 1: Download video
        console.print(f"[bold]Downloading:[/bold] {lesson_title}")
        if not self._download_video(video_url, video_path):
            return 0

        # Step 2: Check for existing subtitles (SRT)
        srt_path = screenshot_dir / "subtitles.srt"
        self._download_subtitles(video_url, srt_path)

        # Step 3: Get video duration
        duration = self._get_duration(video_path)

        # Step 4: Extract screenshots at scene changes
        console.print("[bold]Extracting screenshots...[/bold]")
        screenshots = self._extract_screenshots(video_path, screenshot_dir)

        # Step 5: Transcribe
        if srt_path.exists():
            console.print("[bold]Using existing subtitles[/bold]")
            segments = self._parse_srt(srt_path)
        else:
            console.print("[bold]Transcribing audio...[/bold]")
            if not self._extract_audio(video_path, audio_path):
                return 0
            segments = self._transcribe(audio_path)

        # Step 6: Generate markdown
        md_content = self._generate_markdown(
            title=lesson_title,
            course_id=course_id,
            video_url=video_url,
            duration=duration,
            segments=segments,
            screenshots=screenshots,
            slug=slug,
        )

        md_path = output_dir / f"{slug}.md"
        md_path.write_text(md_content, encoding="utf-8")
        console.print(f"[green]Saved:[/green] {md_path}")

        # Clean up video and audio (keep screenshots)
        video_path.unlink(missing_ok=True)
        audio_path.unlink(missing_ok=True)

        return 1

    def _download_video(self, url: str, output_path: pathlib.Path) -> bool:
        """Download video via yt-dlp."""
        if not shutil.which("yt-dlp"):
            console.print("[red]yt-dlp not found. Install with: pip install yt-dlp[/red]")
            return False
        try:
            result = subprocess.run(
                ["yt-dlp", "-o", str(output_path), "--no-playlist", url],
                capture_output=True, text=True, timeout=600,
            )
            return result.returncode == 0 and output_path.exists()
        except Exception as e:
            console.print(f"[red]Download failed: {e}[/red]")
            return False

    def _download_subtitles(self, url: str, output_path: pathlib.Path) -> bool:
        """Try to download subtitles via yt-dlp."""
        if not shutil.which("yt-dlp"):
            return False
        try:
            result = subprocess.run(
                ["yt-dlp", "--skip-download", "--write-subs", "--write-auto-subs",
                 "--sub-lang", "en", "--sub-format", "srt",
                 "-o", str(output_path.with_suffix("")), url],
                capture_output=True, text=True, timeout=60,
            )
            # yt-dlp adds language suffix, find the file
            for srt in output_path.parent.glob("*.srt"):
                if srt != output_path:
                    srt.rename(output_path)
                    return True
            return output_path.exists()
        except Exception:
            return False

    def _get_duration(self, video_path: pathlib.Path) -> str:
        """Get video duration via ffprobe."""
        if not shutil.which("ffprobe"):
            return "unknown"
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
                capture_output=True, text=True, timeout=30,
            )
            seconds = float(result.stdout.strip())
            return str(timedelta(seconds=int(seconds)))
        except Exception:
            return "unknown"

    def _extract_screenshots(
        self, video_path: pathlib.Path, output_dir: pathlib.Path
    ) -> list[tuple[str, str]]:
        """Extract screenshots at scene changes. Returns list of (timestamp, filename)."""
        if not shutil.which("ffmpeg"):
            console.print("[yellow]ffmpeg not found, skipping screenshots[/yellow]")
            return []
        try:
            # Scene detection with threshold
            subprocess.run(
                ["ffmpeg", "-i", str(video_path), "-vf",
                 "select='gt(scene,0.3)',showinfo", "-vsync", "vfr",
                 str(output_dir / "screenshot-%04d.png"),
                 "-y", "-loglevel", "quiet"],
                capture_output=True, text=True, timeout=300,
            )
            # Also extract at regular intervals as fallback (every 60 seconds)
            subprocess.run(
                ["ffmpeg", "-i", str(video_path), "-vf", "fps=1/60",
                 str(output_dir / "interval-%04d.png"),
                 "-y", "-loglevel", "quiet"],
                capture_output=True, text=True, timeout=300,
            )
        except Exception as e:
            console.print(f"[yellow]Screenshot extraction failed: {e}[/yellow]")

        screenshots = []
        for png in sorted(output_dir.glob("*.png")):
            # Extract timestamp from filename or use index
            idx = len(screenshots)
            timestamp = _format_timestamp(idx * 60)  # approximate
            screenshots.append((timestamp, png.name))
        return screenshots

    def _extract_audio(self, video_path: pathlib.Path, audio_path: pathlib.Path) -> bool:
        """Extract audio from video via ffmpeg."""
        if not shutil.which("ffmpeg"):
            console.print("[red]ffmpeg not found[/red]")
            return False
        try:
            result = subprocess.run(
                ["ffmpeg", "-i", str(video_path), "-vn", "-acodec", "pcm_s16le",
                 "-ar", "16000", "-ac", "1", str(audio_path), "-y", "-loglevel", "quiet"],
                capture_output=True, text=True, timeout=300,
            )
            return result.returncode == 0 and audio_path.exists()
        except Exception as e:
            console.print(f"[red]Audio extraction failed: {e}[/red]")
            return False

    def _transcribe(self, audio_path: pathlib.Path) -> list[tuple[str, str]]:
        """Transcribe audio via faster-whisper. Returns list of (timestamp, text)."""
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            console.print("[red]faster-whisper not installed. Install with: pip install faster-whisper[/red]")
            return []

        console.print("[dim]Loading Whisper model (first run downloads ~1GB)...[/dim]")
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments_iter, info = model.transcribe(str(audio_path), beam_size=5)

        segments = []
        for segment in segments_iter:
            timestamp = _format_timestamp(int(segment.start))
            segments.append((timestamp, segment.text.strip()))
        return segments

    def _parse_srt(self, srt_path: pathlib.Path) -> list[tuple[str, str]]:
        """Parse an SRT file into (timestamp, text) segments."""
        content = srt_path.read_text(encoding="utf-8", errors="replace")
        segments = []
        current_time = None

        for line in content.split("\n"):
            line = line.strip()
            # Match timestamp line: 00:01:23,456 --> 00:01:25,789
            time_match = re.match(r"(\d{2}):(\d{2}):(\d{2})", line)
            if time_match and "-->" in line:
                h, m, s = int(time_match.group(1)), int(time_match.group(2)), int(time_match.group(3))
                current_time = _format_timestamp(h * 3600 + m * 60 + s)
            elif line and not line.isdigit() and current_time:
                # Strip HTML tags from subtitle text
                clean = re.sub(r"<[^>]+>", "", line)
                if clean.strip():
                    segments.append((current_time, clean.strip()))
                    current_time = None

        # Merge segments with same timestamp and consolidate into ~30 second chunks
        return _merge_segments(segments, chunk_seconds=30)

    def _generate_markdown(
        self,
        title: str,
        course_id: int,
        video_url: str,
        duration: str,
        segments: list[tuple[str, str]],
        screenshots: list[tuple[str, str]],
        slug: str,
    ) -> str:
        """Generate timestamped markdown from transcript and screenshots."""
        from datetime import datetime, timezone

        frontmatter = f"""---
lecture: "{title}"
course_id: {course_id}
duration: "{duration}"
video_url: "{video_url}"
transcribed: {datetime.now(timezone.utc).isoformat()}
---"""

        body = f"\n\n# {title}\n"

        # Insert screenshots alongside transcript segments
        screenshot_iter = iter(screenshots)
        current_screenshot = next(screenshot_iter, None)

        for timestamp, text in segments:
            body += f"\n## [{timestamp}]\n\n{text}\n"

            # Insert screenshot if we have one near this timestamp
            if current_screenshot:
                body += f"\n![Slide](./{slug}/{current_screenshot[1]})\n"
                current_screenshot = next(screenshot_iter, None)

        return frontmatter + body


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def _format_timestamp(seconds: int) -> str:
    """Format seconds as HH:MM:SS."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _merge_segments(
    segments: list[tuple[str, str]], chunk_seconds: int = 30
) -> list[tuple[str, str]]:
    """Merge small transcript segments into larger chunks."""
    if not segments:
        return []

    def _parse_ts(ts: str) -> int:
        parts = ts.split(":")
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

    merged = []
    current_ts = segments[0][0]
    current_text = []
    current_start = _parse_ts(segments[0][0])

    for ts, text in segments:
        ts_seconds = _parse_ts(ts)
        if ts_seconds - current_start > chunk_seconds and current_text:
            merged.append((current_ts, " ".join(current_text)))
            current_ts = ts
            current_text = [text]
            current_start = ts_seconds
        else:
            current_text.append(text)

    if current_text:
        merged.append((current_ts, " ".join(current_text)))

    return merged
