import pytest

import rw_io
import trace
from wsfactory import edit_hypothesis, edit_jsonl, make_good_workspace

P = rw_io.PATHS


@pytest.fixture
def ws(tmp_path):
    return make_good_workspace(tmp_path / "ws")


def errors(ws):
    return trace.trace(ws).errors


def test_good_workspace_traces(ws):
    r = trace.trace(ws)
    assert r.errors == []
    assert r.summary["untested_hypotheses"] == ["H-002"]
    assert r.summary["unused_observations"] == ["O-002"]
    assert r.summary["hypotheses_by_origin"] == {"literature": 1, "expert": 1}
    assert r.summary["open_comments"] == ["K-002"]


def test_fresh_workspace(tmp_path):
    rw_io.write_json(tmp_path / "rw" / "state.json", {"gates": {}})
    assert trace.trace(tmp_path).ok


def test_support_level():
    assert trace.compute_support_level(["E-001"]) == "literature"
    assert trace.compute_support_level(["O-001"]) == "expert-opinion"
    assert trace.compute_support_level(["R-001", "R-002"]) == "experimental"
    assert trace.compute_support_level(["E-001", "O-001"]) == "mixed"


def test_dangling_evidence(ws):
    rows = [r for r in rw_io.read_jsonl(ws / P["evidence"]) if r["id"] != "E-002"]
    rw_io.write_jsonl(ws / P["evidence"], rows)
    assert any("dangling reference E-002" in e for e in errors(ws))


def test_wrong_support_level(ws):
    edit_jsonl(ws / P["claims"], "C-003", support_level="literature")
    assert any("C-003: support_level" in e for e in errors(ws))


def test_hypothesis_without_checks(ws):
    edit_hypothesis(ws, "H-002", literature_checks=[])
    assert any("H-002: no literature_checks" in e for e in errors(ws))


def test_expert_hypothesis_needs_both_directions(ws):
    edit_hypothesis(ws, "H-002", literature_checks=["Q-002"])
    assert any("H-002: origin=expert needs" in e for e in errors(ws))


def test_failed_search_does_not_count(ws):
    rows = rw_io.read_csv(ws / P["search_log"])
    (ws / P["search_log"]).unlink()
    for r in rows:
        if r["query_id"] == "Q-003":
            r["status"] = "error"
        rw_io.append_csv(ws / P["search_log"], r, rw_io.SEARCH_LOG_FIELDS)
    assert any(e.startswith("H-002:") for e in errors(ws))


def test_proposed_hypothesis_only_warns(ws):
    edit_hypothesis(ws, "H-002", literature_checks=[], status="proposed")
    r = trace.trace(ws)
    assert not any(e.startswith("H-002") for e in r.errors)
    assert any(w.startswith("H-002") for w in r.warnings)


def test_unconfirmed_observation(ws):
    edit_jsonl(ws / P["observations"], "O-001", confirmed_by_user=False)
    assert any("O-001: not confirmed" in e for e in errors(ws))


def test_excluded_study_with_evidence(ws):
    rw_io.append_csv(ws / P["screening"], dict(id="S-002", stage="full-text", decision="exclude",
                                               reason_code="EX-POP", confidence="0.8", reviewer="u",
                                               timestamp="t", protocol_version="1"), rw_io.SCREENING_FIELDS)
    assert any("E-003: study S-002 is not screened as include" in e for e in errors(ws))


def test_result_from_failed_run(ws):
    edit_jsonl(ws / "experiments" / "X-001" / "results.jsonl", "R-002", run_id="RUN-002")
    assert any("R-002" in e and "failed" in e for e in errors(ws))


def test_runs_before_g3(ws):
    state = rw_io.read_json(ws / P["state"])
    state["gates"]["G3"]["approved_ids"] = []
    rw_io.write_json(ws / P["state"], state)
    assert any("X-001: has runs but was never approved at G3" in e for e in errors(ws))


def test_report_cites_unknown_claim(ws):
    with (ws / P["report"]).open("a", encoding="utf-8") as f:
        f.write("Extra [C-009].\n")
    assert any("[C-009]" in e for e in errors(ws))


def test_rejected_evidence_still_cited(ws):
    edit_jsonl(ws / P["evidence"], "E-001", verification_status="rejected")
    assert any("E-001: rejected evidence is still cited" in e for e in errors(ws))


def test_cli(ws, capsys):
    assert trace.main(["--workspace", str(ws)]) == 0
    edit_jsonl(ws / P["claims"], "C-003", support_level="literature")
    assert trace.main(["--workspace", str(ws)]) == 1
    assert "ERROR" in capsys.readouterr().out
