"""Cross-platform sound playback. Failures are swallowed — a missing speaker
is not worth crashing the watcher over."""
from __future__ import annotations

import logging
import pathlib
import sys
from typing import Literal

log = logging.getLogger(__name__)

Kind = Literal["new_thread", "followup", "escalation", "error"]

try:
    import playsound3  # type: ignore
    _HAVE_PLAYSOUND = True
except Exception:  # pragma: no cover — environment-specific
    _HAVE_PLAYSOUND = False

if sys.platform == "win32":
    try:
        import winsound  # type: ignore
    except Exception:  # pragma: no cover
        winsound = None  # type: ignore[assignment]


def play(kind: Kind, sound_files: dict[str, pathlib.Path]) -> None:
    """Play the configured sound for the given event kind. Best-effort —
    logs and continues on any error."""
    path = str(sound_files[kind])
    try:
        if _HAVE_PLAYSOUND:
            playsound3.playsound(path, block=False)
            return
        if sys.platform == "win32" and "winsound" in globals() and winsound is not None:
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return
        log.debug("No sound backend available for kind=%s; silent", kind)
    except Exception as e:  # pragma: no cover — best-effort
        log.warning("Sound playback failed for %s: %s", kind, e)
