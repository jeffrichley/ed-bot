"""Textual Message wrappers that carry headless-loop emissions into the app.

The loop's ``emit`` callback is sync and must not touch widgets directly. It
wraps each Pydantic result in a ``LoopEmission`` and posts it; the app routes by
``payload`` type. This keeps the loop fully decoupled from the widget tree."""
from __future__ import annotations

from typing import Any

from textual.message import Message


class LoopEmission(Message):
    """One emission from the CockpitLoop (a QueueUpdate / StatusUpdate /
    ActionResult), delivered to the app as a Textual message."""

    def __init__(self, payload: Any) -> None:
        super().__init__()
        self.payload = payload
