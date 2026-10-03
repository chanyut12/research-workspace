"""Regression tests for the whole-branch review findings (C1, C2, I1-I5)."""
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

import audit
import experiment
import net
import rw_io
import rw_state
import search
import trace
import validate
import verify_doi
from wsfactory import edit_hypothesis, edit_jsonl, make_good_workspace, set_stage

ROOT = Path(__file__).resolve().parent.parent
P = rw_io.PATHS


@pytest.fixture
def ws(tmp_path):
    return make_good_workspace(tmp_path / "my ws")


# C1 ---------------------------------------------------------------------------
def test_c1_parallel_searches_get_distinct_query_ids(ws):
    def slow_fetch(url, params=None, headers=None):
        time.sleep(0.2)
        return {"results": [{"id": "W9", "title": "t", "publication_year": 2020}]}
    rows = []
    threads = [threading.Thread(target=lambda: rows.append(
        search.run_search(ws, "openalex", "q", "scoping", "", fetch=slow_fetch))) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(r["query_id"] for r in rows) == ["Q-004", "Q-005"]
    assert validate.validate_file(ws / P["search_log"], ws) == []


def test_c1_duplicate_query_ids_are_reported(ws):
    row = rw_io.read_csv(ws / P["search_log"])[0]
    rw_io.append_csv(ws / P["search_log"], row, rw_io.SEARCH_LOG_FIELDS)
    assert any("duplicate id Q-001" in e for e in validate.validate_file(ws / P["search_log"], ws))


def test_c1_discovery_agent_does_not_merge():
    assert "dedupe.py" not in (ROOT / "agents" / "discovery-agent.md").read_text(encoding="utf-8")


# C2 ---------------------------------------------------------------------------
def guard(payload, *flags, py=sys.executable):
    r = subprocess.run([py, *flags, str(ROOT / "scripts" / "hook_guard.py")], input=json.dumps(payload),
                       capture_output=True, text=True)
    return r.returncode


@pytest.mark.parametrize("cmd", [
    'sh "/a b/scripts/rw" rw_state.py --workspace "/Users/x/buu 4.1/stroke" approve G1',
    "python3 rw_state.py --workspace=/tmp/w approve G4",
    "python3 -m rw_state approve G2",
    'python3 -c "import rw_state; rw_state.approve(\'.\', \'G4\')"',
])
def test_c2_approve_variants_blocked(cmd):
    assert guard({"tool_name": "Bash", "tool_input": {"command": cmd}}) == 2


@pytest.mark.parametrize("cmd", [
    "cat > protocol/protocol.yaml <<EOF\nx\nEOF",
    "sed -i '' 's/en/th/' protocol/protocol.yaml",
    "echo '{}' > rw/state.json",
    "cp /tmp/x experiments/X-001/spec.yaml",
])
def test_c2_bash_writes_to_frozen_files_blocked(ws, cmd):
    assert guard({"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(ws)}) == 2


def test_c2_harmless_bash_allowed(ws):
    for cmd in ("cat protocol/protocol.yaml", 'sh "/x/scripts/rw" rw_state.py status',
                "python3 train.py > experiments/X-001/outputs/log.txt"):
        assert guard({"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(ws)}) == 0, cmd


def test_c2_tampering_detected_by_hash(ws):
    set_stage(ws, "SCOPED")
    state = rw_io.read_json(ws / P["state"])
    state["gates"]["G1"]["approved"] = False
    rw_io.write_json(ws / P["state"], state)
    rw_state.approve(ws, "G1")
    assert trace.trace(ws).ok
    with (ws / P["protocol"]).open("a", encoding="utf-8") as f:
        f.write("# sneaky edit\n")
    assert any("protocol/protocol.yaml changed after approval" in e for e in trace.trace(ws).errors)


# I1 ---------------------------------------------------------------------------
def test_i1_workspace_flag_after_subcommand(ws):
    assert audit.main(["evidence", "E-002", "--status", "verified", "--workspace", str(ws)]) == 0
    assert audit.main(["status", "--workspace", str(ws)]) == 0
    assert rw_state.main(["status", "--workspace", str(ws)]) == 0


def test_i1_agents_always_use_wrapper():
    for f in (ROOT / "agents").glob("*.md"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if ".py " in line and "`" in line and "scripts" not in line and "experiment.py" in line:
                assert 'sh "<scripts_dir>/rw"' in line, (f.name, line)


# I2 ---------------------------------------------------------------------------
def test_i2_g2_rejects_bad_based_on(ws):
    set_stage(ws, "SYNTHESIZED")
    edit_hypothesis(ws, "H-002", status="proposed", based_on=["O-009"])
    with pytest.raises(rw_state.GateError, match="O-009"):
        rw_state.approve(ws, "G2")
    edit_jsonl(ws / P["observations"], "O-001", confirmed_by_user=False)
    edit_hypothesis(ws, "H-002", based_on=["O-001"])
    with pytest.raises(rw_state.GateError, match="not confirmed"):
        rw_state.approve(ws, "G2")


# I3 ---------------------------------------------------------------------------
def test_i3_non_crossref_doi_checked_in_openalex():
    rec = {"id": "S-009", "title": "Deep learning stroke outcome", "year": 2023, "doi": "10.48550/arxiv.2301.00001"}

    def fetch(url, params=None, headers=None):
        if "crossref" in url:
            raise net.NotFound("404")
        return {"title": "Deep learning stroke outcome", "publication_year": 2023}
    r = verify_doi.verify_record(rec, fetch=fetch)
    assert r["status"] == "verified" and "non-Crossref" in r["detail"]


# I4 ---------------------------------------------------------------------------
def test_i4_guard_works_without_third_party_packages(ws):
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(ws / P["protocol"])}}
    assert guard(payload, "-S") == 2


@pytest.mark.skipif(not Path("/usr/bin/python3").exists(), reason="no system python")
def test_i4_guard_runs_on_system_python(ws):
    payload = {"tool_name": "Bash", "tool_input": {"command": "python3 rw_state.py approve G1"}}
    assert guard(payload, py="/usr/bin/python3") == 2


# I5 ---------------------------------------------------------------------------
def test_i5_append_after_missing_trailing_newline(tmp_path):
    p = tmp_path / "o.jsonl"
    p.write_text('{"id": "O-001"}', encoding="utf-8")
    rw_io.append_jsonl(p, {"id": "O-002"})
    assert [r["id"] for r in rw_io.read_jsonl(p)] == ["O-001", "O-002"]
    c = tmp_path / "s.csv"
    c.write_text("a,b\r\n1,2", encoding="utf-8")
    rw_io.append_csv(c, {"a": 3, "b": 4}, ["a", "b"])
    assert rw_io.read_csv(c) == [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]
