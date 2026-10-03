import pytest

import comments
import rw_io
from wsfactory import make_good_workspace

P = rw_io.PATHS


@pytest.fixture
def ws(tmp_path):
    return make_good_workspace(tmp_path / "ws")


def test_summarize(ws):
    s = comments.summarize(ws)
    assert s["total"] == 2
    assert s["open"] == ["K-002"]
    assert s["open_must"] == []
    assert s["by_status"]["addressed"] == 1


def test_addressed_needs_changed_ids(ws):
    with pytest.raises(ValueError, match="--changed"):
        comments.resolve(ws, "K-002", "addressed")


def test_declined_needs_reason(ws):
    with pytest.raises(ValueError, match="--resolution"):
        comments.resolve(ws, "K-002", "declined")


def test_deferred_needs_until(ws):
    with pytest.raises(ValueError, match="--until"):
        comments.resolve(ws, "K-002", "deferred")


def test_unknown_comment_and_ids(ws):
    with pytest.raises(ValueError, match="unknown comment"):
        comments.resolve(ws, "K-099", "declined", resolution="x")
    with pytest.raises(ValueError, match="unknown IDs"):
        comments.resolve(ws, "K-002", "addressed", changed_ids=["X-404"])


def test_resolve_persists_and_logs(ws):
    comments.resolve(ws, "K-002", "declined", resolution="label already validated by registry")
    row = [c for c in rw_io.read_jsonl(ws / P["comments"]) if c["id"] == "K-002"][0]
    assert row["status"] == "declined"
    last = rw_io.read_jsonl(ws / P["decision_log"])[-1]
    assert last["kind"] == "note" and "K-002" in last["cause_ids"]


def test_render_markdown_escapes_pipes():
    md = comments.render_markdown([{"id": "K-001", "meeting_id": "M-001", "target": "general",
                                    "severity": "must", "status": "open", "text": "a | b\nc",
                                    "resolution": None, "changed_ids": [], "deferred_until": None}])
    assert "a \\| b c" in md
    assert comments.render_markdown([]).startswith("_")
