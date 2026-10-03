import pytest

import claims
import experiment
import rw_io
import trace
import validate
from wsfactory import make_good_workspace

P = rw_io.PATHS
DS = {"name": "stroke-registry", "version": "2026-09", "path": "data/registry.csv"}


@pytest.fixture
def ws(tmp_path):
    return make_good_workspace(tmp_path / "ws")


def new_x2(ws):
    return experiment.new_experiment(ws, "H-002", "Test H-002", DS, "patient-level 80/20",
                                     ["auroc", "auprc"], "auroc", [1, 2], "bootstrap CI")


def test_new_experiment(ws):
    d = new_x2(ws)
    assert d.name == "X-002" and (d / "outputs").is_dir()
    assert validate.validate_file(d / "spec.yaml", ws) == []
    assert rw_io.read_yaml(d / "spec.yaml")["status"] == "draft"


def test_new_experiment_checks(ws):
    with pytest.raises(ValueError, match="H-404"):
        experiment.new_experiment(ws, "H-404", "x", DS, "s", ["auroc"], "auroc", [1], "p")
    with pytest.raises(ValueError, match="primary"):
        experiment.new_experiment(ws, "H-002", "x", DS, "s", ["auroc"], "f1", [1], "p")


def test_log_run_requires_g3(ws):
    new_x2(ws)
    with pytest.raises(ValueError, match="G3"):
        experiment.log_run(ws, "X-002", "ok")
    run = experiment.log_run(ws, "X-001", "failed", params={"model": "rf"}, notes="NaN loss")
    assert run["run_id"] == "RUN-003"
    assert validate.validate_file(ws / "experiments" / "X-001" / "runs.jsonl", ws) == []


def test_add_result_rules(ws):
    with pytest.raises(ValueError, match="status ok"):
        experiment.add_result(ws, "X-001", "RUN-002", "auroc", 0.7, "test", "x")
    with pytest.raises(ValueError, match="pre-registered"):
        experiment.add_result(ws, "X-001", "RUN-001", "accuracy", 0.9, "test", "x")
    r = experiment.add_result(ws, "X-001", "RUN-001", "auroc", 0.805, "validation", "val AUROC", ci=(0.77, 0.83))
    assert r["id"] == "R-003"
    assert trace.trace(ws).ok


def test_add_claim(ws):
    c = claims.add_claim(ws, "Experts and our data agree", ["O-001", "R-001"], "Discussion")
    assert c["id"] == "C-005" and c["support_level"] == "mixed"
    assert validate.validate_file(ws / P["claims"], ws) == []
    with pytest.raises(ValueError, match="E-404"):
        claims.add_claim(ws, "x", ["E-404"])
    with pytest.raises(ValueError, match="at least one"):
        claims.add_claim(ws, "x", [])
    with pytest.raises(ValueError, match="H-001"):
        claims.add_claim(ws, "x", ["H-001"])


def test_list_claims(ws):
    out = claims.render_list(ws)
    assert "[C-003] (expert-opinion)" in out
