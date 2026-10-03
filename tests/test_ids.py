import pytest

import ids
import rw_io
from wsfactory import make_good_workspace


@pytest.fixture
def ws(tmp_path):
    return make_good_workspace(tmp_path / "ws")


@pytest.mark.parametrize("prefix,expected", [
    ("S", "S-003"), ("E", "E-004"), ("H", "H-003"), ("X", "X-002"), ("R", "R-003"),
    ("Q", "Q-004"), ("RQ", "RQ-2"), ("M", "M-003"), ("O", "O-003"), ("K", "K-003"), ("C", "C-005")])
def test_next_id_continues(ws, prefix, expected):
    assert ids.next_id(ws, prefix) == expected


def test_empty_workspace(tmp_path):
    rw_io.write_json(tmp_path / "rw" / "state.json", {})
    assert ids.next_id(tmp_path, "S") == "S-001"
    assert ids.next_id(tmp_path, "RQ") == "RQ-1"


def test_next_run_id(ws):
    assert ids.next_run_id(ws, "X-001") == "RUN-003"
    assert ids.next_run_id(ws, "X-009") == "RUN-001"


def test_beyond_999(ws):
    rw_io.append_jsonl(ws / rw_io.PATHS["claims"], {"id": "C-1000"})
    assert ids.next_id(ws, "C") == "C-1001"


def test_unknown_prefix(ws):
    with pytest.raises(ValueError):
        ids.next_id(ws, "Z")


def test_all_ids(ws):
    every = ids.all_ids(ws)
    assert {"RQ-1", "Q-003", "S-002", "E-003", "M-002", "O-002", "K-002", "H-002", "X-001", "R-002", "C-004"} <= every
