import pytest

import rw_io


def _ws(root):
    (root / "rw").mkdir(parents=True)
    (root / "rw" / "state.json").write_text("{}", encoding="utf-8")
    return root


def test_find_workspace_walks_up(tmp_path):
    ws = _ws(tmp_path / "ws")
    sub = ws / "literature" / "raw"
    sub.mkdir(parents=True)
    assert rw_io.find_workspace(sub) == ws.resolve()
    assert rw_io.find_workspace(sub / "not-yet-written.json") == ws.resolve()


def test_find_workspace_none(tmp_path):
    assert rw_io.find_workspace(tmp_path) is None


def test_path_with_spaces(tmp_path):
    ws = _ws(tmp_path / "my research ws")
    assert rw_io.find_workspace(ws / "report") == ws.resolve()


def test_resolve_workspace_outside_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(rw_io.NotInWorkspace, match="rw/state.json"):
        rw_io.resolve_workspace()


def test_jsonl_thai_roundtrip(tmp_path):
    p = tmp_path / "o.jsonl"
    rw_io.append_jsonl(p, {"statement": "คนไข้ AF มาช้า"})
    assert "คนไข้" in p.read_text(encoding="utf-8")
    assert rw_io.read_jsonl(p) == [{"statement": "คนไข้ AF มาช้า"}]


def test_read_jsonl_reports_line(tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text('{"a": 1}\n{bad\n', encoding="utf-8")
    with pytest.raises(ValueError, match=":2:"):
        rw_io.read_jsonl(p)


def test_read_csv_handles_excel_bom_crlf(tmp_path):
    p = tmp_path / "s.csv"
    p.write_bytes("﻿id,decision\r\nS-001,include\r\n".encode("utf-8"))
    assert rw_io.read_csv(p) == [{"id": "S-001", "decision": "include"}]


def test_append_csv_header_once(tmp_path):
    p = tmp_path / "log.csv"
    rw_io.append_csv(p, {"a": 1, "b": None}, ["a", "b"])
    rw_io.append_csv(p, {"a": 2, "b": "x"}, ["a", "b"])
    assert rw_io.read_csv(p) == [{"a": "1", "b": ""}, {"a": "2", "b": "x"}]


def test_yaml_roundtrip_thai(tmp_path):
    p = tmp_path / "h.yaml"
    rw_io.write_yaml(p, {"statement": "สมมติฐาน"})
    assert "สมมติฐาน" in p.read_text(encoding="utf-8")
    assert rw_io.read_yaml(p) == {"statement": "สมมติฐาน"}
    assert rw_io.read_yaml(tmp_path / "missing.yaml") is None
