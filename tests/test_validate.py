import pytest

import rw_io
import validate
from wsfactory import edit_jsonl, make_good_workspace

P = rw_io.PATHS


@pytest.fixture
def ws(tmp_path):
    return make_good_workspace(tmp_path / "ws")


def test_good_workspace_is_valid(ws):
    assert validate.validate_workspace(ws) == []


def test_rule_for():
    assert validate.rule_for("meetings/M-001-2026-10-05-expert-consult/meeting.yaml") == ("meeting", "yaml")
    assert validate.rule_for("experiments/X-001/results.jsonl") == ("result", "jsonl")
    assert validate.rule_for("data/registry.csv") is None
    assert validate.rule_for("meetings/M-001-x/notes.md") is None


def test_evidence_without_anchor(ws):
    edit_jsonl(ws / P["evidence"], "E-001",
               source_location={"page": None, "section": None, "table": None, "figure": None})
    errs = validate.validate_workspace(ws)
    assert any(e.startswith("literature/evidence.jsonl:1: source_location") for e in errs), errs


def test_duplicate_ids(ws):
    rows = rw_io.read_jsonl(ws / P["claims"])
    rw_io.append_jsonl(ws / P["claims"], rows[0])
    errs = validate.validate_workspace(ws)
    assert any("duplicate id C-001" in e for e in errs), errs


def test_comment_addressed_needs_changed_ids(ws):
    edit_jsonl(ws / P["comments"], "K-001", changed_ids=[])
    errs = validate.validate_file(ws / P["comments"], ws)
    assert any("meetings/comments.jsonl:1: changed_ids" in e for e in errs), errs


def test_csv_errors_report_row_number(ws):
    rows = rw_io.read_csv(ws / P["screening"])
    rows[0]["decision"] = "maybe"
    (ws / P["screening"]).unlink()
    for r in rows:
        rw_io.append_csv(ws / P["screening"], r, rw_io.SCREENING_FIELDS)
    errs = validate.validate_file(ws / P["screening"], ws)
    assert any(e.startswith("literature/screening.csv:2: decision") for e in errs), errs


def test_unparseable_yaml(ws):
    (ws / P["hypotheses"]).write_text("hypotheses: [unclosed", encoding="utf-8")
    errs = validate.validate_file(ws / P["hypotheses"], ws)
    assert errs and "cannot parse" in errs[0]


def test_data_dir_is_skipped(ws):
    (ws / "data").mkdir()
    (ws / "data" / "records.jsonl").write_text("{not json", encoding="utf-8")
    assert validate.validate_workspace(ws) == []


def test_cli_exit_codes(ws, capsys):
    assert validate.main(["--workspace", str(ws)]) == 0
    edit_jsonl(ws / P["claims"], "C-001", cites=[])
    assert validate.main(["--workspace", str(ws)]) == 1
    assert "report/claims.jsonl:1: cites" in capsys.readouterr().out
