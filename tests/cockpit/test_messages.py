"""Tests for the Textual message wrappers carrying loop emissions."""
from ed_bot.cockpit.models import QueueUpdate, StatusUpdate
from ed_bot.cockpit.messages import LoopEmission


def test_loop_emission_carries_payload():
    payload = StatusUpdate(line="drafting #207...")
    msg = LoopEmission(payload)
    assert msg.payload is payload


def test_loop_emission_accepts_queue_update():
    payload = QueueUpdate(items=[])
    msg = LoopEmission(payload)
    assert isinstance(msg.payload, QueueUpdate)
