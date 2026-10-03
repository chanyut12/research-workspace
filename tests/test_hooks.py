import json
import subprocess
import sys
from pathlib import Path

import pytest

import rw_io
from wsfactory import edit_jsonl, make_good_workspace

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
P = rw_io.PATHS


def run_hook(name, payload, *flags):
    r = subprocess.run([sys.executable, *flags, str(SCRIPTS / name)], input=json.dumps(payload),
                       capture_output=True, text=True)
    return r.returncode, r.stderr


@pytest.fixture
def ws(tmp_path):
    return make_good_workspace(tmp_path / "my research ws")


def write(path):
    return {"tool_name": "Write", "tool_input": {"file_path": str(path)}, "cwd": "/"}


def test_validate_passes_good_file(ws):
    assert run_hook("hook_validate.py", write(ws / P["evidence"]))[0] == 0


def test_validate_blocks_broken_artifact(ws):
    edit_jsonl(ws / P["evidence"], "E-001", extractor_confidence=3)
    code, err = run_hook("hook_validate.py", write(ws / P["evidence"]))
    assert code == 2 and "literature/evidence.jsonl:1: extractor_confidence" in err


def test_validate_ignores_non_artifacts(ws, tmp_path):
    assert run_hook("hook_validate.py", write(ws / "meetings" / "x" / "notes.md"))[0] == 0
    assert run_hook("hook_validate.py", write(tmp_path / "elsewhere.jsonl"))[0] == 0
    assert run_hook("hook_validate.py", {"tool_name": "Write", "tool_input": {}})[0] == 0


def test_validate_relative_path_uses_cwd(ws):
    edit_jsonl(ws / P["claims"], "C-001", cites=[])
    payload = {"tool_name": "Edit", "tool_input": {"file_path": "report/claims.jsonl"}, "cwd": str(ws)}
    assert run_hook("hook_validate.py", payload)[0] == 2


def test_validate_without_deps_does_not_block(ws):
    edit_jsonl(ws / P["evidence"], "E-001", extractor_confidence=3)
    assert run_hook("hook_validate.py", write(ws / P["evidence"]), "-S")[0] == 0


def test_guard_blocks_model_approval():
    bash = {"tool_name": "Bash", "tool_input": {"command": 'python3 "/x/scripts/rw_state.py" approve G1'}}
    code, err = run_hook("hook_guard.py", bash)
    assert code == 2 and "/rw-approve" in err
    ok = {"tool_name": "Bash", "tool_input": {"command": "python3 scripts/rw_state.py status"}}
    assert run_hook("hook_guard.py", ok)[0] == 0


def test_guard_protocol_frozen_after_g1(ws):
    code, err = run_hook("hook_guard.py", write(ws / P["protocol"]))
    assert code == 2 and "amendments" in err
    state = rw_io.read_json(ws / P["state"])
    state["gates"]["G1"]["approved"] = False
    rw_io.write_json(ws / P["state"], state)
    assert run_hook("hook_guard.py", write(ws / P["protocol"]))[0] == 0


def test_guard_spec_frozen_after_g3(ws):
    assert run_hook("hook_guard.py", write(ws / "experiments" / "X-001" / "spec.yaml"))[0] == 2
    assert run_hook("hook_guard.py", write(ws / "experiments" / "X-002" / "spec.yaml"))[0] == 0


def test_guard_state_files(ws):
    assert run_hook("hook_guard.py", write(ws / P["state"]))[0] == 2
    assert run_hook("hook_guard.py", write(ws / P["decision_log"]))[0] == 2
    assert run_hook("hook_guard.py", write(ws / P["evidence"]))[0] == 0


def test_hooks_json_points_to_existing_scripts():
    cfg = json.loads((ROOT / "hooks" / "hooks.json").read_text())
    cmds = [h["command"] for event in cfg["hooks"].values() for m in event for h in m["hooks"]]
    assert len(cmds) == 2
    for c in cmds:
        name = c.split('/scripts/rw" ')[1]
        assert (SCRIPTS / name).exists() and c.startswith('sh "${CLAUDE_PLUGIN_ROOT}/scripts/rw"')
