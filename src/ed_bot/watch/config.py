"""Parse and validate ~/.ed-bot/watch.yaml."""
from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import yaml

_DURATION_RE = re.compile(r"^(\d+)([smh])$")
_HOURS_RE = re.compile(r"^(\d{2}):(\d{2})-(\d{2}):(\d{2})$")
_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class ScheduleError(ValueError):
    """Raised when watch.yaml's schedule is invalid (overlap, bad day, etc.)."""


@dataclass
class Window:
    days: list[str]
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int
    interval_seconds: Optional[int]  # None means "off"

    def contains(self, dt: datetime) -> bool:
        day = _DAYS[dt.weekday()]
        if day not in self.days:
            return False
        start = self.start_hour * 60 + self.start_minute
        end = self.end_hour * 60 + self.end_minute
        now = dt.hour * 60 + dt.minute
        if start <= end:
            return start <= now < end
        # Wraps midnight (e.g., 22:00-09:00).
        return now >= start or now < end


@dataclass
class WatchConfig:
    course_id: Optional[int]
    windows: list[Window] = field(default_factory=list)
    sounds: dict[str, pathlib.Path] = field(default_factory=dict)

    def window_for(self, dt: datetime) -> Optional[Window]:
        for w in self.windows:
            if w.contains(dt):
                return w
        return None


def parse_duration(s: str) -> Optional[int]:
    """Parse '5m', '30s', '1h', or 'off'. Returns seconds, or None for 'off'."""
    if s == "off":
        return None
    m = _DURATION_RE.match(s)
    if not m:
        raise ValueError(f"Invalid interval: {s!r} (expected like '5m', '30s', '1h', or 'off')")
    n, unit = int(m.group(1)), m.group(2)
    return n * {"s": 1, "m": 60, "h": 3600}[unit]


def parse_hours(s: str) -> tuple[int, int, int, int]:
    m = _HOURS_RE.match(s)
    if not m:
        raise ValueError(f"Invalid hours: {s!r} (expected HH:MM-HH:MM)")
    return tuple(int(g) for g in m.groups())  # type: ignore[return-value]


def _validate_no_overlap(windows: list[Window]) -> None:
    """Two windows on the same day must not overlap (wrap-around aware)."""
    spans: list[tuple[str, int, int]] = []
    for w in windows:
        s = w.start_hour * 60 + w.start_minute
        e = w.end_hour * 60 + w.end_minute
        for day in w.days:
            if s < e:
                spans.append((day, s, e))
            else:
                # Wrap: [s, 1440) and [0, e)
                spans.append((day, s, 1440))
                spans.append((day, 0, e))
    by_day: dict[str, list[tuple[int, int]]] = {}
    for day, s, e in spans:
        by_day.setdefault(day, []).append((s, e))
    for day, items in by_day.items():
        items.sort()
        for i in range(1, len(items)):
            if items[i][0] < items[i - 1][1]:
                raise ScheduleError(
                    f"Overlapping schedule windows on {day}: "
                    f"{items[i - 1]} and {items[i]}"
                )


def load(path: pathlib.Path, ed_bot_dir: pathlib.Path) -> WatchConfig:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    windows: list[Window] = []
    for entry in data.get("schedule", []):
        days = entry.get("days", [])
        for d in days:
            if d not in _DAYS:
                raise ScheduleError(f"Unknown day: {d!r} (must be one of {_DAYS})")
        sh, sm, eh, em = parse_hours(entry["hours"])
        windows.append(Window(
            days=list(days),
            start_hour=sh, start_minute=sm,
            end_hour=eh, end_minute=em,
            interval_seconds=parse_duration(str(entry["interval"])),
        ))

    _validate_no_overlap(windows)

    sounds: dict[str, pathlib.Path] = {}
    for k, v in (data.get("sounds") or {}).items():
        sounds[k] = pathlib.Path(str(v).replace("{ed_bot}", str(ed_bot_dir)))

    return WatchConfig(
        course_id=data.get("course_id"),
        windows=windows,
        sounds=sounds,
    )
