"""The cockpit agent must keep a stray ANTHROPIC_API_KEY out of the SDK env.

EdClient (built for posting) calls load_dotenv, which leaks the project .env's
ANTHROPIC_API_KEY into the process. The SDK authenticates via the Max-plan
subscription, so that stale key must be scrubbed before launching a query, or
the SDK subprocess fails with "Invalid API key".
"""
import os

from ed_bot.cockpit.agent import _scrub_conflicting_api_key


def test_scrub_removes_anthropic_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-stale-from-dotenv")
    assert os.environ.get("ANTHROPIC_API_KEY") == "sk-stale-from-dotenv"
    _scrub_conflicting_api_key()
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_scrub_is_a_noop_when_key_absent(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Must not raise when the key was never set.
    _scrub_conflicting_api_key()
    assert "ANTHROPIC_API_KEY" not in os.environ
