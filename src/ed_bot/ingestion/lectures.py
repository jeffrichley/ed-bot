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
        lesson_id: int | None = None,
        slide_id: int | None = None,
        slide_title: str | None = None,
        region: str = "us",
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

        # Step 4: Transcribe
        if srt_path.exists():
            console.print("[bold]Using existing subtitles[/bold]")
            segments = self._parse_srt(srt_path)
        else:
            console.print("[bold]Transcribing audio...[/bold]")
            if not self._extract_audio(video_path, audio_path):
                return 0
            segments = self._transcribe(audio_path)
            audio_path.unlink(missing_ok=True)

        # Step 5: Generate markdown (no pre-extracted screenshots — frames pulled on demand)
        md_content = self._generate_markdown(
            title=lesson_title,
            course_id=course_id,
            video_url=video_url,
            duration=duration,
            segments=segments,
            slug=slug,
            lesson_id=lesson_id,
            slide_id=slide_id,
            slide_title=slide_title,
            region=region,
        )

        md_path = output_dir / f"{slug}.md"
        md_path.write_text(md_content, encoding="utf-8")
        console.print(f"[green]Saved:[/green] {md_path}")

        return 1

    def _download_video(self, url: str, output_path: pathlib.Path) -> bool:
        """Download video via yt-dlp Python API."""
        try:
            import yt_dlp
        except ImportError:
            console.print("[red]yt-dlp not installed. Add it with: uv add yt-dlp[/red]")
            return False
        try:
            ydl_opts = {
                "outtmpl": str(output_path),
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "format": "best[ext=mp4]/best",
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            # yt-dlp may add extension, find the actual file
            if output_path.exists():
                return True
            for f in output_path.parent.glob(f"{output_path.stem}*"):
                if f.suffix in (".mp4", ".mkv", ".webm"):
                    f.rename(output_path)
                    return True
            return False
        except Exception as e:
            console.print(f"[red]Download failed: {e}[/red]")
            return False

    def _download_subtitles(self, url: str, output_path: pathlib.Path) -> bool:
        """Try to download subtitles via yt-dlp Python API."""
        try:
            import yt_dlp
        except ImportError:
            return False
        try:
            ydl_opts = {
                "outtmpl": str(output_path.with_suffix("")),
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": ["en"],
                "subtitlesformat": "srt",
                "quiet": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
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
        slug: str,
        lesson_id: int | None = None,
        slide_id: int | None = None,
        slide_title: str | None = None,
        region: str = "us",
    ) -> str:
        """Generate timestamped markdown from transcript.

        No pre-extracted screenshots — frames are pulled on demand via
        extract_frame() when the drafter references a specific timestamp.
        The video file is stored at ./{slug}/video.mp4 for this purpose.
        """
        from datetime import datetime, timezone

        # Build EdStem deep link
        edstem_url = ""
        if lesson_id:
            edstem_url = f"https://edstem.org/{region}/courses/{course_id}/lessons/{lesson_id}"
            if slide_id:
                edstem_url += f"/slides/{slide_id}"

        frontmatter = f"""---
lecture: "{title}"
course_id: {course_id}
lesson_id: {lesson_id or 'null'}
slide_id: {slide_id or 'null'}
slide_title: "{slide_title or ''}"
duration: "{duration}"
video_url: "{video_url}"
video_file: "{slug}/video.mp4"
edstem_url: "{edstem_url}"
transcribed: {datetime.now(timezone.utc).isoformat()}
---"""

        body = f"\n\n# {title}\n"
        if edstem_url:
            body += f"\n> Watch on EdStem: [{title}]({edstem_url})\n"

        for timestamp, text in segments:
            body += f"\n## [{timestamp}]\n\n{text}\n"

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


def extract_frame(video_path: pathlib.Path, timestamp: str, output_path: pathlib.Path) -> bool:
    """Extract a single frame from a video at a specific timestamp.

    Args:
        video_path: Path to the video file
        timestamp: Timestamp in HH:MM:SS format
        output_path: Where to save the PNG

    Returns True on success, False on failure.
    Used by the drafter to pull frames on demand when referencing lectures.
    """
    if not shutil.which("ffmpeg"):
        return False
    try:
        result = subprocess.run(
            ["ffmpeg", "-ss", timestamp, "-i", str(video_path),
             "-frames:v", "1", "-q:v", "2", str(output_path),
             "-y", "-loglevel", "quiet"],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0 and output_path.exists()
    except Exception:
        return False


def find_video_for_lecture(lectures_dir: pathlib.Path, slug: str) -> pathlib.Path | None:
    """Find the stored video file for a lecture by its slug.

    Returns the video path or None if not found.
    """
    video_path = lectures_dir / slug / "video.mp4"
    if video_path.exists():
        return video_path
    # Try finding any video file in the slug directory
    slug_dir = lectures_dir / slug
    if slug_dir.exists():
        for ext in ("*.mp4", "*.mkv", "*.webm"):
            videos = list(slug_dir.glob(ext))
            if videos:
                return videos[0]
    return None
