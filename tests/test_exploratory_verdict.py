"""v0.2: exploratory experiments (data exploration lane) and hypothesis verdicts."""
import pytest

import claims
import experiment
import hypotheses
import rw_io
import rw_state
import trace
import validate
from wsfactory import edit_hypothesis, make_good_workspace, set_stage

P = rw_io.PATHS
DS = {"name": "stroke-registry", "version": "2026-09", "path": "data/registry.csv"}


@pytest.fixture
def ws(tmp_path):
    return make_good_workspace(tmp_path / "ws")


def explore(ws):
    d = experiment.new_experiment(ws, None, "EDA of onset time by AF status", DS, kind="exploratory")
    run = experiment.log_run(ws, d.name, "ok", notes="notebooks/eda.ipynb")
    res = experiment.add_result(ws, d.name, run["run_id"], "night_onset_rate_af", 0.42, "all", "AF night onset share")
    return d.name, res["id"]


# exploratory lane ---------------------------------------------------------------
def test_exploratory_needs_no_hypothesis_or_g3(ws):
    xid, rid = explore(ws)
    spec = rw_io.read_yaml(ws / "experiments" / xid / "spec.yaml")
    assert spec["kind"] == "exploratory" and spec["hypothesis_id"] is None
    assert validate.validate_workspace(ws) == []
    assert trace.trace(ws).ok


def test_confirmatory_still_needs_hypothesis(ws):
    with pytest.raises(ValueError, match="hypothesis"):
        experiment.new_experiment(ws, None, "x", DS, "s", ["auroc"], "auroc", [1], "p")


def test_g3_rejects_exploratory(ws):
    xid, _ = explore(ws)
    set_stage(ws, "HYPOTHESES_APPROVED")
    with pytest.raises(rw_state.GateError, match="exploratory"):
        rw_state.approve(ws, "G3", ids=[xid])


def test_claims_label_exploratory_results(ws):
    _, rid = explore(ws)
    c = claims.add_claim(ws, "In exploration, 42% of AF strokes had night onset", [rid])
    assert c["support_level"] == "exploratory"
    with pytest.raises(ValueError, match="exploratory"):
        claims.add_claim(ws, "mixed", [rid, "E-001"])


def test_trace_rejects_hand_written_mixed_claim(ws):
    _, rid = explore(ws)
    rw_io.append_jsonl(ws / P["claims"], {"id": "C-009", "text": "x", "cites": [rid, "E-001"],
                                          "support_level": "mixed", "section": None})
    assert any("C-009" in e and "exploratory" in e for e in trace.trace(ws).errors)


def test_circular_confirmation_warned(ws):
    xid, rid = explore(ws)
    data = rw_io.read_yaml(ws / P["hypotheses"])
    data["hypotheses"].append({"id": "H-003", "rq_id": "RQ-1", "statement": "AF night onset predicts delay",
                               "origin": "data-exploration", "based_on": [rid], "literature_checks": ["Q-003"],
                               "status": "approved", "rationale": None})
    rw_io.write_yaml(ws / P["hypotheses"], data)
    experiment.new_experiment(ws, "H-003", "confirm H-003", DS, "patient-level 80/20", ["auroc"], "auroc", [1], "p")
    assert any("H-003" in w and "same data" in w for w in trace.trace(ws).warnings)


# verdicts ----------------------------------------------------------------------
def test_record_verdict(ws):
    edit_hypothesis(ws, "H-001", status="approved", verdict=None)
    h = hypotheses.record_verdict(ws, "H-001", "refuted", ["R-001"], ["E-001"], "AUROC gain was not significant")
    assert h["status"] == "tested" and h["verdict"]["outcome"] == "refuted"
    assert validate.validate_workspace(ws) == []
    assert rw_io.read_jsonl(ws / P["decision_log"])[-1]["ids"] == ["H-001", "R-001", "E-001"]


def test_verdict_rules(ws):
    edit_hypothesis(ws, "H-001", status="approved", verdict=None)
    with pytest.raises(ValueError, match="rationale"):
        hypotheses.record_verdict(ws, "H-001", "supported", ["R-001"], [], "")
    with pytest.raises(ValueError, match="H-002"):
        hypotheses.record_verdict(ws, "H-002", "supported", ["R-001"], [], "x")
    _, rid = explore(ws)
    with pytest.raises(ValueError, match="exploratory"):
        hypotheses.record_verdict(ws, "H-001", "supported", [rid], [], "x")
    with pytest.raises(ValueError, match="outcome"):
        hypotheses.record_verdict(ws, "H-001", "maybe", ["R-001"], [], "x")


def test_trace_verdict_rules(ws):
    edit_hypothesis(ws, "H-001", verdict=None)
    assert any("H-001: status tested but no verdict" in e for e in trace.trace(ws).errors)
    edit_hypothesis(ws, "H-001", status="approved")
    assert any("H-001: has results but no verdict" in w for w in trace.trace(ws).warnings)


def test_writing_requires_verdicts(ws):
    set_stage(ws, "RESULTS_VALIDATED")
    edit_hypothesis(ws, "H-001", status="approved", verdict=None)
    with pytest.raises(rw_state.GateError, match="H-001"):
        rw_state.advance(ws, "WRITING")
    hypotheses.record_verdict(ws, "H-001", "inconclusive", ["R-001"], [], "CI overlaps baseline")
    assert rw_state.advance(ws, "WRITING")["stage"] == "WRITING"
