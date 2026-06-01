import pytest

pytestmark = pytest.mark.anyio


class _FakeThreadDetail:
    def __init__(self, is_answered):
        self.is_answered = is_answered


class _FakeThreads:
    def __init__(self, detail):
        self._detail = detail
        self.got = []

    def get(self, thread_id):
        self.got.append(thread_id)
        return self._detail


class _FakeClient:
    def __init__(self, *, is_answered=False):
        self.threads = _FakeThreads(_FakeThreadDetail(is_answered))
        self.comments = None
        self.closed = False

    def close(self):
        self.closed = True


async def test_is_answered_fn_returns_thread_flag():
    from ed_bot.cockpit.backends import build_is_answered_fn
    client = _FakeClient(is_answered=True)
    is_answered = build_is_answered_fn(client=client)
    assert await is_answered(99887) is True
    assert client.threads.got == [99887]
