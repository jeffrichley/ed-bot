"""Tests for play() — cross-platform sound dispatch."""
import pathlib
from unittest.mock import patch, MagicMock
import pytest
from ed_bot.watch import sound as sound_mod


@pytest.fixture
def sound_files(tmp_path):
    return {
        "new_thread": tmp_path / "new.wav",
        "followup": tmp_path / "followup.wav",
        "escalation": tmp_path / "escalation.wav",
        "error": tmp_path / "error.wav",
    }


def test_play_uses_playsound3_when_available(sound_files):
    with patch.object(sound_mod, "_HAVE_PLAYSOUND", True), \
         patch.object(sound_mod, "playsound3", create=True) as mock_ps:
        sound_mod.play("new_thread", sound_files)
        mock_ps.playsound.assert_called_once_with(
            str(sound_files["new_thread"]), block=False
        )


def test_play_passes_correct_file_per_kind(sound_files):
    with patch.object(sound_mod, "_HAVE_PLAYSOUND", True), \
         patch.object(sound_mod, "playsound3", create=True) as mock_ps:
        sound_mod.play("escalation", sound_files)
        mock_ps.playsound.assert_called_once_with(
            str(sound_files["escalation"]), block=False
        )


def test_play_falls_back_to_winsound_on_windows(sound_files, monkeypatch):
    monkeypatch.setattr(sound_mod.sys, "platform", "win32")
    fake_winsound = MagicMock()
    fake_winsound.SND_FILENAME = 0x20000
    fake_winsound.SND_ASYNC = 0x1
    with patch.object(sound_mod, "_HAVE_PLAYSOUND", False), \
         patch.object(sound_mod, "winsound", fake_winsound, create=True):
        sound_mod.play("new_thread", sound_files)
        fake_winsound.PlaySound.assert_called_once_with(
            str(sound_files["new_thread"]),
            fake_winsound.SND_FILENAME | fake_winsound.SND_ASYNC,
        )


def test_play_is_silent_on_non_windows_without_playsound(sound_files, monkeypatch):
    monkeypatch.setattr(sound_mod.sys, "platform", "darwin")
    with patch.object(sound_mod, "_HAVE_PLAYSOUND", False):
        # Should not raise.
        sound_mod.play("new_thread", sound_files)


def test_play_does_not_raise_when_playsound_errors(sound_files):
    with patch.object(sound_mod, "_HAVE_PLAYSOUND", True), \
         patch.object(sound_mod, "playsound3", create=True) as mock_ps:
        mock_ps.playsound.side_effect = RuntimeError("audio device busy")
        sound_mod.play("new_thread", sound_files)  # Should not raise.
