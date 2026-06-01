"""Tests for parsing typed chat text into a UserCommand."""
from ed_bot.cockpit.command_parser import parse_command
from ed_bot.cockpit.models import UserCommand


def test_check_forum():
    cmd = parse_command("check the forum")
    assert cmd.intent == "check_forum"


def test_open_with_number():
    cmd = parse_command("answer 207")
    assert cmd.intent == "open"
    assert cmd.thread == 207


def test_open_with_hash_number():
    cmd = parse_command("open #212")
    assert cmd.intent == "open"
    assert cmd.thread == 212


def test_post_it_is_approve():
    assert parse_command("post it").intent == "approve"


def test_edit_carries_text():
    cmd = parse_command("make it more Socratic", active_thread=207)
    assert cmd.intent == "edit"
    assert cmd.thread == 207
    assert cmd.text == "make it more Socratic"


def test_unknown_is_freeform():
    cmd = parse_command("what's the weather", active_thread=None)
    assert cmd.intent == "freeform"
    assert cmd.text == "what's the weather"
