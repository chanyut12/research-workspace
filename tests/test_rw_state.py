import pytest

import audit
import rw_io
import rw_state
from wsfactory import edit_hypothesis, edit_jsonl, make_good_workspace, set_stage

P = rw_io.PATHS


@pytest.fixture
def ws(tmp_path):
    return make_good_workspace(tmp_path / "ws")


def fresh(tmp_path):
    rw_io.write_json(tmp_path / P["state"], rw_state.new_state("T"))
    return tmp_path


def test_new_state():
    s = rw_state.new_state("Stroke")
    assert s["stage"] == "INIT" and not s["gates"]["G1"]["approved"]


def test_scoped_requires_protocol(tmp_path, ws):
    w = fresh(tmp_path / "f")
    with pytest.raises(rw_state.GateError, match="does not exist"):
        rw_state.advance(w, "SCOPED")
    (w / "protocol").mkdir()
    (w / P["protocol"]).write_bytes((ws / P["protocol"]).read_bytes())
    assert rw_state.advance(w, "SCOPED")["stage"] == "SCOPED"
    assert rw_io.read_jsonl(w / P["decision_log"])[-1]["to"] == "SCOPED"


def test_cannot_jump_or_stay(ws):
    with pytest.raises(ValueError, match="cannot jump"):
        rw_state.advance(ws, "RELEASED")
    with pytest.raises(ValueError, match="already"):
        rw_state.advance(ws, "WRITING")


def test_g1_flow(ws):
    set_stage(ws, "SCOPED")
    state = rw_io.read_json(ws / P["state"])
    state["gates"]["G1"]["approved"] = False
    rw_io.write_json(ws / P["state"], state)
    with pytest.raises(rw_state.GateError, match="G1 is not approved"):
        rw_state.advance(ws, "PROTOCOL_APPROVED")
    s = rw_state.approve(ws, "G1", note="ok")
    assert s["gates"]["G1"]["approved"] and s["protocol_version"] == 1
    assert rw_state.advance(ws, "PROTOCOL_APPROVED")["stage"] == "PROTOCOL_APPROVED"


def test_g1_wrong_stage(ws):
    with pytest.raises(rw_state.GateError, match="SCOPED"):
        rw_state.approve(ws, "G1")


def test_g2_requires_literature_checks(ws):
    set_stage(ws, "SYNTHESIZED")
    edit_hypothesis(ws, "H-002", status="proposed", literature_checks=[])
    with pytest.raises(rw_state.GateError, match="H-002: no literature_checks"):
        rw_state.approve(ws, "G2")
    edit_hypothesis(ws, "H-002", literature_checks=["Q-003"])
    s = rw_state.approve(ws, "G2")
    assert "H-002" in s["gates"]["G2"]["approved_ids"]
    assert rw_io.read_yaml(ws / P["hypotheses"])["hypotheses"][1]["status"] == "approved"


def test_g2_rejects_non_proposed(ws):
    with pytest.raises(rw_state.GateError, match="only proposed"):
        rw_state.approve(ws, "G2", ids=["H-001"])


def test_g3(ws):
    set_stage(ws, "HYPOTHESES_APPROVED")
    with pytest.raises(rw_state.GateError, match="explicit experiment IDs"):
        rw_state.approve(ws, "G3")
    spec = rw_io.read_yaml(ws / "experiments" / "X-001" / "spec.yaml")
    spec.update(id="X-002", hypothesis_id="H-009", status="draft")
    rw_io.write_yaml(ws / "experiments" / "X-002" / "spec.yaml", spec)
    with pytest.raises(rw_state.GateError, match="not approved at G2"):
        rw_state.approve(ws, "G3", ids=["X-002"])
    spec["hypothesis_id"] = "H-002"
    rw_io.write_yaml(ws / "experiments" / "X-002" / "spec.yaml", spec)
    s = rw_state.approve(ws, "G3", ids=["X-002"])
    assert s["gates"]["G3"]["approved_ids"] == ["X-001", "X-002"]
    assert rw_io.read_yaml(ws / "experiments" / "X-002" / "spec.yaml")["status"] == "approved"


def test_audited_and_g4(ws):
    assert rw_state.advance(ws, "AUDITED")["stage"] == "AUDITED"
    assert rw_state.approve(ws, "G4")["gates"]["G4"]["approved"]
    assert rw_state.advance(ws, "RELEASED")["stage"] == "RELEASED"


def test_g4_blocked_by_open_must_comment(ws):
    set_stage(ws, "AUDITED")
    edit_jsonl(ws / P["comments"], "K-002", severity="must")
    with pytest.raises(rw_state.GateError, match="K-002"):
        rw_state.approve(ws, "G4")


def test_audited_blocked_by_weaken(ws):
    audit.add_review(ws, "C-001", "WEAKEN", "too strong")
    with pytest.raises(rw_state.GateError, match="WEAKEN"):
        rw_state.advance(ws, "AUDITED")


def test_backward_needs_reason_and_resets_g4(ws):
    set_stage(ws, "AUDITED")
    rw_state.approve(ws, "G4")
    with pytest.raises(ValueError, match="--reason"):
        rw_state.advance(ws, "LITERATURE")
    s = rw_state.advance(ws, "LITERATURE", reason="advisor asked for more literature", cause_ids=["K-002"])
    assert s["stage"] == "LITERATURE" and not s["gates"]["G4"]["approved"]
    assert rw_io.read_jsonl(ws / P["decision_log"])[-1]["cause_ids"] == ["K-002"]


def test_amend(ws, tmp_path):
    proto = rw_io.read_yaml(ws / P["protocol"])
    proto["eligibility"]["exclude"].append("Paediatric stroke")
    amend = ws / "protocol" / "amendments" / "2026-11-01-exclude-paeds.yaml"
    rw_io.write_yaml(amend, proto)
    with pytest.raises(ValueError, match="protocol_version: 2"):
        rw_state.amend_protocol(ws, amend, note="advisor request")
    proto["protocol_version"] = 2
    rw_io.write_yaml(amend, proto)
    with pytest.raises(ValueError, match="--note"):
        rw_state.amend_protocol(ws, amend, note="")
    s = rw_state.amend_protocol(ws, amend, note="advisor request")
    assert s["protocol_version"] == 2
    assert "Paediatric stroke" in rw_io.read_yaml(ws / P["protocol"])["eligibility"]["exclude"]
    assert rw_io.read_jsonl(ws / P["decision_log"])[-1]["kind"] == "amend"


def test_amend_before_g1(tmp_path):
    w = fresh(tmp_path)
    with pytest.raises(ValueError, match="before G1"):
        rw_state.amend_protocol(w, w / "x.yaml", note="n")


def test_cli(ws, capsys):
    assert rw_state.main(["--workspace", str(ws), "status"]) == 0
    out = capsys.readouterr().out
    assert "WRITING" in out and "AUDITED" in out
    assert rw_io.run_cli(rw_state.main, ["--workspace", str(ws), "approve", "G1"]) == 1
