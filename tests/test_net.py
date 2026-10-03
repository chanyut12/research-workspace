import io
import json
import urllib.error

import pytest

import net


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener_from(outcomes):
    calls = []

    def opener(req, timeout=30):
        calls.append(req.full_url)
        o = outcomes[len(calls) - 1]
        if isinstance(o, int):
            raise urllib.error.HTTPError(req.full_url, o, "err", {}, None)
        return FakeResp(json.dumps(o).encode())
    return opener, calls


def test_success_with_params():
    opener, calls = opener_from([{"ok": 1}])
    assert net.get_json("https://x.org/a", {"q": "stroke risk"}, opener=opener) == {"ok": 1}
    assert calls == ["https://x.org/a?q=stroke+risk"]


def test_retries_then_succeeds():
    opener, calls = opener_from([503, 429, {"ok": 2}])
    sleeps = []
    assert net.get_json("https://x.org", opener=opener, sleep=sleeps.append) == {"ok": 2}
    assert sleeps == [1.0, 2.0]


def test_404_is_not_retried():
    opener, calls = opener_from([404])
    with pytest.raises(net.NotFound):
        net.get_json("https://x.org", opener=opener, sleep=lambda s: None)
    assert len(calls) == 1


def test_gives_up_after_retries():
    opener, calls = opener_from([503, 503, 503])
    with pytest.raises(net.RetrievalError, match="3 attempts"):
        net.get_json("https://x.org", opener=opener, sleep=lambda s: None)


def test_client_error_not_retried():
    opener, calls = opener_from([400])
    with pytest.raises(net.RetrievalError, match="HTTP 400"):
        net.get_json("https://x.org", opener=opener, sleep=lambda s: None)
    assert len(calls) == 1
