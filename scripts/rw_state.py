"""Workflow state machine: stages, human gates G1–G4 and protocol amendments (spec section 6)."""
from __future__ import annotations

import argparse
from pathlib import Path

import audit
import comments
import rw_io
import trace
import validate

P = rw_io.PATHS
STAGES = ["INIT", "SCOPED", "PROTOCOL_APPROVED", "LITERATURE", "SYNTHESIZED", "HYPOTHESES_APPROVED",
          "EXPERIMENTING", "RESULTS_VALIDATED", "WRITING", "AUDITED", "RELEASED"]
GATES = ("G1", "G2", "G3", "G4")
REQUIRED_GATE = {"PROTOCOL_APPROVED": "G1", "HYPOTHESES_APPROVED": "G2", "EXPERIMENTING": "G3", "RELEASED": "G4"}


class GateError(ValueError):
    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


def _fresh_gate() -> dict:
    return {"approved": False, "approved_at": None, "approved_ids": [], "note": None}


def new_state(title: str) -> dict:
    return {"schema_version": 1, "title": title, "stage": "INIT", "protocol_version": 0,
            "gates": {g: _fresh_gate() for g in GATES}}


def load_state(ws) -> dict:
    return rw_io.read_json(Path(ws) / P["state"])


def save_state(ws, state) -> None:
    rw_io.write_json(Path(ws) / P["state"], state)


def log_decision(ws, kind, **fields) -> None:
    entry = {"timestamp": rw_io.now_iso(), "kind": kind, "from": None, "to": None, "gate": None,
             "ids": [], "reason": None, "cause_ids": []}
    entry.update(fields)
    rw_io.append_jsonl(Path(ws) / P["decision_log"], entry)


def _idx(stage: str) -> int:
    return STAGES.index(stage)


def preconditions(ws, state, target) -> list[str]:
    """Problems that block moving forward into `target` (empty list = allowed)."""
    ws = Path(ws)
    gates = state["gates"]
    problems = []
    if target == "SCOPED":
        p = ws / P["protocol"]
        problems += validate.validate_file(p, ws) if p.exists() else \
            ["protocol/protocol.yaml does not exist (draft it with /rw-protocol)"]
    elif target in REQUIRED_GATE:
        gate = REQUIRED_GATE[target]
        if gate in ("G2", "G3"):
            if not gates[gate]["approved_ids"]:
                problems.append(f"{gate} has no approved items yet (the user runs /rw-approve {gate})")
        elif not gates[gate]["approved"]:
            problems.append(f"{gate} is not approved (the user runs /rw-approve {gate})")
    elif target == "SYNTHESIZED":
        if not (rw_io.read_yaml(ws / P["hypotheses"]) or {}).get("hypotheses"):
            problems.append("synthesis/hypotheses.yaml has no hypotheses yet")
    elif target == "RESULTS_VALIDATED":
        with_results = {r.get("experiment_id") for r in trace.load_graph(ws)["results"].values()}
        problems += [f"{x}: no results recorded" for x in gates["G3"]["approved_ids"] if x not in with_results]
        problems += validate.validate_workspace(ws)
    elif target == "WRITING":
        g = trace.load_graph(ws)
        problems += [f"{h}: has confirmatory results but no verdict (conclude it with /rw-experiment conclude {h})"
                     for h, v in sorted(g["hypotheses"].items())
                     if not v.get("verdict") and trace.confirmatory_results_for(g, h)]
    elif target == "AUDITED":
        problems += trace.trace(ws).errors
        problems += audit.blocking_issues(ws)
    return problems


def advance(ws, target, reason="", cause_ids=None) -> dict:
    if target not in STAGES:
        raise ValueError(f"unknown stage {target}; one of {', '.join(STAGES)}")
    state = load_state(ws)
    cur = state["stage"]
    if target == cur:
        raise ValueError(f"already at {cur}")
    if _idx(target) == _idx(cur) + 1:
        problems = preconditions(ws, state, target)
        if problems:
            raise GateError(problems)
    elif _idx(target) < _idx(cur):
        if target == "INIT":
            raise ValueError("cannot move back to INIT")
        if not (reason or "").strip():
            raise ValueError("moving back requires --reason (and --cause with the K/H/X IDs behind it)")
        if _idx(target) < _idx("AUDITED"):
            state["gates"]["G4"] = _fresh_gate()
    else:
        nxt = STAGES[_idx(cur) + 1] if cur != "RELEASED" else "(none)"
        raise ValueError(f"cannot jump from {cur} to {target}; the next stage is {nxt}")
    state["stage"] = target
    save_state(ws, state)
    log_decision(ws, "advance", **{"from": cur, "to": target, "reason": reason or None,
                                   "cause_ids": list(cause_ids or [])})
    return state


def approve(ws, gate, ids=None, note=None) -> dict:
    ws = Path(ws)
    state = load_state(ws)
    stage = state["stage"]
    if gate not in GATES:
        raise ValueError(f"unknown gate {gate}; one of {', '.join(GATES)}")
    problems, new_ids = [], []
    if gate == "G1":
        if stage != "SCOPED":
            problems.append(f"G1 is approved at stage SCOPED (current stage {stage})")
        proto = ws / P["protocol"]
        problems += validate.validate_file(proto, ws) if proto.exists() else ["protocol/protocol.yaml does not exist"]
        if problems:
            raise GateError(problems)
        state["protocol_version"] = (rw_io.read_yaml(proto) or {}).get("protocol_version", 1)
        state.setdefault("frozen", {})[P["protocol"]] = trace.frozen_digest(ws, P["protocol"])
    elif gate == "G2":
        if _idx(stage) < _idx("SYNTHESIZED"):
            problems.append(f"G2 needs stage SYNTHESIZED or later (current stage {stage})")
        hpath = ws / P["hypotheses"]
        if hpath.exists():
            problems += validate.validate_file(hpath, ws)
            if problems:
                raise GateError(problems)
        data = rw_io.read_yaml(hpath) or {"schema_version": 1, "hypotheses": []}
        by = {h["id"]: h for h in data["hypotheses"]}
        new_ids = list(ids) if ids else [h for h, v in by.items() if v.get("status") == "proposed"]
        if not new_ids:
            problems.append("no proposed hypotheses to approve")
        for hid in new_ids:
            if hid not in by:
                problems.append(f"{hid}: does not exist")
            elif by[hid].get("status") != "proposed":
                problems.append(f"{hid}: status is {by[hid].get('status')}; only proposed hypotheses can be approved")
        problems += trace.check_hypotheses(trace.load_graph(ws), [h for h in new_ids if h in by])
        if problems:
            raise GateError(problems)
        for hid in new_ids:
            by[hid]["status"] = "approved"
        rw_io.write_yaml(hpath, data)
    elif gate == "G3":
        if _idx(stage) < _idx("HYPOTHESES_APPROVED"):
            problems.append(f"G3 needs stage HYPOTHESES_APPROVED or later (current stage {stage})")
        if not ids:
            problems.append("G3 needs explicit experiment IDs, e.g. /rw-approve G3 X-001")
        for xid in ids or []:
            spath = ws / "experiments" / xid / "spec.yaml"
            if not spath.exists():
                problems.append(f"{xid}: experiments/{xid}/spec.yaml does not exist")
                continue
            problems += validate.validate_file(spath, ws)
            if (rw_io.read_yaml(spath) or {}).get("kind") == "exploratory":
                problems.append(f"{xid}: exploratory experiments need no G3; only confirmatory ones are pre-registered")
                continue
            hyp = (rw_io.read_yaml(spath) or {}).get("hypothesis_id")
            if hyp not in state["gates"]["G2"]["approved_ids"]:
                problems.append(f"{xid}: hypothesis {hyp} is not approved at G2")
        if problems:
            raise GateError(problems)
        for xid in ids:
            spath = ws / "experiments" / xid / "spec.yaml"
            spec = rw_io.read_yaml(spath)
            spec["status"] = "approved"
            rw_io.write_yaml(spath, spec)
            rel = f"experiments/{xid}/spec.yaml"
            state.setdefault("frozen", {})[rel] = trace.frozen_digest(ws, rel)
        new_ids = list(ids)
    else:  # G4
        if stage != "AUDITED":
            problems.append(f"G4 is approved at stage AUDITED (current stage {stage})")
        problems += trace.trace(ws).errors
        problems += [f"{k}: must-fix comment is still open" for k in comments.summarize(ws)["open_must"]]
        problems += audit.blocking_issues(ws)
        if problems:
            raise GateError(problems)
    g = state["gates"][gate]
    g.update(approved=True, approved_at=rw_io.now_iso(), note=note,
             approved_ids=sorted(set(g["approved_ids"]) | set(new_ids)))
    save_state(ws, state)
    log_decision(ws, "approve", gate=gate, ids=new_ids, reason=note)
    return state


def amend_protocol(ws, amendment_file, note) -> dict:
    ws = Path(ws).resolve()
    state = load_state(ws)
    if not state["gates"]["G1"]["approved"]:
        raise ValueError("before G1 there is nothing to amend: edit protocol/protocol.yaml directly")
    if not (note or "").strip():
        raise ValueError("an amendment needs --note <reason>")
    src = Path(amendment_file)
    src = (src if src.is_absolute() else ws / src).resolve()
    if not src.is_relative_to(ws / "protocol" / "amendments") or not src.exists():
        raise ValueError("the amendment file must exist under protocol/amendments/")
    new = rw_io.read_yaml(src)
    expected = state["protocol_version"] + 1
    if not isinstance(new, dict) or new.get("protocol_version") != expected:
        raise ValueError(f"the amendment must contain the full protocol with protocol_version: {expected}")
    problems = validate.validate_object("protocol", new, src.relative_to(ws).as_posix())
    if problems:
        raise GateError(problems)
    rw_io.write_yaml(ws / P["protocol"], new)
    state["protocol_version"] = expected
    state.setdefault("frozen", {})[P["protocol"]] = trace.frozen_digest(ws, P["protocol"])
    save_state(ws, state)
    log_decision(ws, "amend", ids=[src.relative_to(ws).as_posix()], reason=note)
    return state


def status_text(ws) -> str:
    state = load_state(ws)
    cur = state["stage"]
    lines = [f"project: {state['title']}", f"stage: {cur} (protocol v{state['protocol_version']})"]
    for g in GATES:
        gate = state["gates"][g]
        extra = f" {', '.join(gate['approved_ids'])}" if gate["approved_ids"] else ""
        lines.append(f"  {g}: {'approved' if gate['approved'] else 'pending'}{extra}")
    if cur != "RELEASED":
        nxt = STAGES[_idx(cur) + 1]
        problems = preconditions(ws, state, nxt)
        lines.append(f"next stage: {nxt} — " + ("ready" if not problems else "blocked by:"))
        lines += [f"  - {p}" for p in problems]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Research workflow state: status, advance, approve.")
    ap.add_argument("--workspace")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", parents=[rw_io.ws_parent()])
    adv = sub.add_parser("advance", parents=[rw_io.ws_parent()])
    adv.add_argument("stage", choices=STAGES)
    adv.add_argument("--reason", default="")
    adv.add_argument("--cause", default="", help="comma-separated IDs (e.g. K-003) that caused the move")
    apr = sub.add_parser("approve", parents=[rw_io.ws_parent()], help="human-only: approve a gate or apply a protocol amendment")
    apr.add_argument("gate", choices=[*GATES, "amend"])
    apr.add_argument("args", nargs="*", help="G2: H-IDs, G3: X-IDs, amend: amendment file")
    apr.add_argument("--note")
    a = ap.parse_args(argv)
    ws = rw_io.resolve_workspace(a.workspace)
    if a.cmd == "status":
        print(status_text(ws))
    elif a.cmd == "advance":
        causes = [c.strip() for c in a.cause.split(",") if c.strip()]
        print(f"stage -> {advance(ws, a.stage, a.reason, causes)['stage']}")
    elif a.gate == "amend":
        if len(a.args) != 1:
            raise ValueError("usage: approve amend protocol/amendments/<file>.yaml --note <reason>")
        print(f"protocol amended -> v{amend_protocol(ws, a.args[0], a.note)['protocol_version']}")
    else:
        state = approve(ws, a.gate, a.args or None, a.note)
        g = state["gates"][a.gate]
        print(f"{a.gate} approved" + (f": {', '.join(g['approved_ids'])}" if g["approved_ids"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(rw_io.run_cli(main))
