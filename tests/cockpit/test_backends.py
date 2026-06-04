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


class _FakeComment:
    def __init__(self, id):
        self.id = id


class _FakeComments:
    def __init__(self, *, accept_raises=False):
        self.posted = []
        self.replied = []
        self.accepted = []
        self._accept_raises = accept_raises

    def post(self, thread_id, content, is_answer=False):
        self.posted.append((thread_id, content, is_answer))
        return _FakeComment(id=4242)

    def reply(self, comment_id, content):
        self.replied.append((comment_id, content))
        return _FakeComment(id=7777)

    def accept(self, comment_id):
        self.accepted.append(comment_id)
        if self._accept_raises:
            raise RuntimeError("Invalid answer ancestor")


class _FakePostThreads:
    """Returns is_answered from a sequence, one per get() call (last repeats)."""
    def __init__(self, answered_seq):
        self._seq = list(answered_seq) or [True]
        self.gets = 0

    def get(self, thread_id):
        i = min(self.gets, len(self._seq) - 1)
        self.gets += 1
        return _FakeThreadDetail(self._seq[i])


class _PostClient:
    def __init__(self, *, accept_raises=False, answered_seq=(True,)):
        self.comments = _FakeComments(accept_raises=accept_raises)
        self.threads = _FakePostThreads(answered_seq)


def _no_sleep(_):
    return None


async def test_post_answer_posts_and_accepts():
    from ed_bot.cockpit.backends import build_post_fn
    client = _PostClient()
    post = build_post_fn(client=client, verify_delay=0, sleep=_no_sleep)
    res = await post(thread_id=500, number=10, body="Here's the answer.",
                     post_kind="answer", target_comment_id=None)
    assert res.ok is True
    assert res.accepted is True
    assert res.posted_id == 4242
    assert client.comments.posted == [(500, "Here's the answer.", True)]
    assert client.comments.accepted == [4242]


async def test_post_answer_warns_when_accept_fails():
    from ed_bot.cockpit.backends import build_post_fn
    client = _PostClient(accept_raises=True)
    post = build_post_fn(client=client, verify_delay=0, sleep=_no_sleep)
    res = await post(thread_id=500, number=10, body="Answer for a post-type thread.",
                     post_kind="answer", target_comment_id=None)
    assert res.ok is True
    assert res.accepted is False
    assert res.posted_id == 4242
    assert "accept" in res.message.lower()


async def test_post_answer_retries_accept_until_thread_confirms():
    """Ed can 200 the accept yet not resolve the just-posted answer. We re-fetch
    and re-accept until the thread actually flips to answered."""
    from ed_bot.cockpit.backends import build_post_fn
    client = _PostClient(answered_seq=[False, False, True])
    post = build_post_fn(client=client, verify_delay=0, sleep=_no_sleep)
    res = await post(thread_id=500, number=10, body="ans",
                     post_kind="answer", target_comment_id=None)
    assert res.accepted is True
    assert len(client.comments.accepted) >= 2     # re-accepted after the no-op
    assert client.threads.gets >= 2               # verified more than once


async def test_post_answer_warns_when_resolution_never_confirms():
    """If the thread never flips to answered, report accepted=False with an
    actionable warning instead of a silent false success."""
    from ed_bot.cockpit.backends import build_post_fn
    client = _PostClient(answered_seq=[False])    # never resolves
    post = build_post_fn(client=client, verify_delay=0, sleep=_no_sleep)
    res = await post(thread_id=500, number=10, body="ans",
                     post_kind="answer", target_comment_id=None)
    assert res.ok is True
    assert res.accepted is False
    assert res.posted_id == 4242
    assert "by hand" in res.message.lower()


async def test_post_answer_trusts_accept_when_unverifiable():
    """If the thread can't be re-fetched, trust the 2xx rather than spam accept."""
    from ed_bot.cockpit.backends import build_post_fn

    class _NoThreads:
        def get(self, thread_id):
            raise RuntimeError("cannot fetch")

    client = _PostClient()
    client.threads = _NoThreads()
    post = build_post_fn(client=client, verify_delay=0, sleep=_no_sleep)
    res = await post(thread_id=500, number=10, body="ans",
                     post_kind="answer", target_comment_id=None)
    assert res.accepted is True
    assert client.comments.accepted == [4242]     # only the single accept


async def test_post_reply_does_not_accept():
    from ed_bot.cockpit.backends import build_post_fn
    client = _PostClient()
    post = build_post_fn(client=client)
    res = await post(thread_id=500, number=10, body="Follow-up reply.",
                     post_kind="reply", target_comment_id=909)
    assert res.ok is True
    assert res.posted_id == 7777
    assert client.comments.replied == [(909, "Follow-up reply.")]
    assert client.comments.accepted == []


async def test_post_returns_not_ok_on_network_error():
    from ed_bot.cockpit.backends import build_post_fn

    class _BoomComments:
        def post(self, *a, **k):
            raise RuntimeError("503 from EdStem")

    class _BoomClient:
        comments = _BoomComments()

    post = build_post_fn(client=_BoomClient())
    res = await post(thread_id=1, number=1, body="x", post_kind="answer",
                     target_comment_id=None)
    assert res.ok is False
    assert "503" in res.message


async def test_fetch_events_collects_watcher_events():
    from ed_bot.cockpit.backends import build_fetch_events
    from ed_bot.cockpit.models import WatcherEvent

    def fake_poll(*, course_id, fetch, store, play, sound_files, on_event):
        on_event("new_thread", thread_id=321, number=7, title="RF indicators",
                 category="Project 8 | Random Forest",
                 url="https://edstem.org/us/courses/1/discussion/321")

    events = build_fetch_events(store=object(), sound_files={},
                                fetch=lambda cid: [], play=lambda *a, **k: None,
                                poll=fake_poll)
    out = await events(1)
    assert len(out) == 1
    ev = out[0]
    assert isinstance(ev, WatcherEvent)
    assert ev.kind == "new_thread"
    assert ev.thread_id == 321
    assert ev.number == 7
    assert ev.title == "RF indicators"


async def test_fetch_events_offloads_to_thread():
    import threading
    from ed_bot.cockpit.backends import build_fetch_events

    main_thread = threading.current_thread().ident
    seen = {}

    def fake_poll(*, course_id, fetch, store, play, sound_files, on_event):
        seen["thread"] = threading.current_thread().ident

    events = build_fetch_events(store=object(), sound_files={},
                                fetch=lambda cid: [], play=lambda *a, **k: None,
                                poll=fake_poll)
    await events(1)
    assert seen["thread"] != main_thread
