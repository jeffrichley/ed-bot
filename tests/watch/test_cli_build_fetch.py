def test_build_fetch_is_importable_and_returns_callable(monkeypatch):
    # build_fetch constructs an EdClient eagerly (moved verbatim from the old
    # inner closure), which needs a token. Provide one so construction works
    # without reaching the network — we only assert the returned fetch is
    # callable, never invoke it.
    monkeypatch.setenv("ED_API_TOKEN", "test-token")
    from ed_bot.watch.cli import build_fetch
    fetch = build_fetch()
    assert callable(fetch)
